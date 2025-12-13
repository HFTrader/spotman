#!/usr/bin/env python3
"""
SpotMan Core - AWS EC2 Instance Management Library
Core functionality for managing AWS EC2 instances with application class tagging.
"""

import os
import sys
import time
import yaml
import base64
from typing import Dict, List, Optional
from functools import wraps

import boto3
from botocore.exceptions import ClientError, NoCredentialsError, EndpointConnectionError, ConnectTimeoutError


# AMI filters for supported operating systems
AMI_FILTERS = {
    'ubuntu': {
        'owner_id': '099720109477',  # Canonical
        'name_pattern': 'ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*'
    },
    'amazon-linux': {
        'owner_id': '137112412989',  # Amazon
        'name_pattern': 'amzn2-ami-hvm-*-x86_64-gp2'
    },
    'centos': {
        'owner_id': '679593333241',  # CentOS Project
        'name_pattern': 'CentOS Linux 7 x86_64 HVM EBS *'
    }
}

# Spot instance status code interpretations
SPOT_STATUS_MESSAGES = {
    'fulfilled': ('✅', 'Spot request fulfilled - instance is running normally'),
    'instance-terminated-by-price': ('💰', 'Instance terminated because spot price exceeded your max bid'),
    'instance-terminated-by-user': ('👤', 'Instance was terminated by user'),
    'instance-terminated-no-capacity': ('📉', 'Instance terminated due to lack of spot capacity'),
    'instance-terminated-capacity-oversubscribed': ('📉', 'Instance terminated - capacity was oversubscribed'),
    'instance-stopped-by-price': ('💰', 'Instance stopped because spot price exceeded your max bid'),
    'instance-stopped-by-user': ('👤', 'Instance was stopped by user'),
    'instance-stopped-no-capacity': ('📉', 'Instance stopped due to lack of spot capacity'),
    'marked-for-termination': ('⚠️', 'Instance is marked for termination (2-minute warning)'),
    'marked-for-stop': ('⚠️', 'Instance is marked for stop (2-minute warning)'),
    'pending-evaluation': ('⏳', 'Spot request is being evaluated'),
    'pending-fulfillment': ('⏳', 'Waiting for spot capacity'),
}


class AWSErrorHandler:
    """Centralized AWS error handling utilities."""
    
    # AWS error codes that indicate transient issues (should be retried)
    RETRYABLE_ERRORS = {
        'Throttling',
        'RequestLimitExceeded',
        'ServiceUnavailable',
        'InternalError',
        'InternalFailure',
        'ServiceUnavailable',
        'SlowDown'
    }
    
    # AWS error codes that indicate permanent failures (should not be retried)
    PERMANENT_ERRORS = {
        'InvalidParameterValue',
        'InvalidInstanceID.NotFound',
        'InvalidInstanceID.Malformed',
        'UnauthorizedOperation',
        'InvalidUserID.NotFound',
        'InvalidGroupId.NotFound',
        'InvalidKeyPair.NotFound',
        'InvalidAMIID.NotFound',
        'InvalidSubnetID.NotFound',
        'InvalidVpcID.NotFound',
        'InvalidSecurityGroupID.NotFound',
        'InstanceLimitExceeded',
        'InsufficientInstanceCapacity',
        'InvalidInstanceType',
        'InvalidAvailabilityZone',
        'InvalidParameterCombination'
    }
    
    @staticmethod
    def should_retry(error_code: str) -> bool:
        """Determine if an AWS error should be retried."""
        return error_code in AWSErrorHandler.RETRYABLE_ERRORS
    
    @staticmethod
    def is_permanent_error(error_code: str) -> bool:
        """Determine if an AWS error indicates a permanent failure."""
        return error_code in AWSErrorHandler.PERMANENT_ERRORS
    
    @staticmethod
    def handle_aws_error(error: ClientError, operation: str = "AWS operation") -> bool:
        """
        Handle AWS errors with appropriate logging and return whether to retry.
        
        Args:
            error: The ClientError exception
            operation: Description of the operation that failed
            
        Returns:
            bool: True if the operation should be retried, False otherwise
        """
        error_code = error.response.get('Error', {}).get('Code', 'Unknown')
        error_message = error.response.get('Error', {}).get('Message', str(error))
        
        print(f"AWS Error during {operation}:")
        print(f"  Error Code: {error_code}")
        print(f"  Message: {error_message}")
        
        if AWSErrorHandler.should_retry(error_code):
            print(f"  → This is a retryable error. Will retry...")
            return True
        elif AWSErrorHandler.is_permanent_error(error_code):
            print(f"  → This is a permanent error. Will not retry.")
            return False
        else:
            print(f"  → Unknown error type. Will not retry.")
            return False
    
    @staticmethod
    def retry_on_aws_error(max_retries: int = 3, delay: float = 1.0):
        """
        Decorator to automatically retry AWS operations on retryable errors.
        
        Args:
            max_retries: Maximum number of retry attempts
            delay: Base delay between retries (exponential backoff)
        """
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                last_error = None
                
                for attempt in range(max_retries + 1):
                    try:
                        return func(*args, **kwargs)
                    except ClientError as e:
                        last_error = e
                        
                        if attempt == max_retries:
                            # Last attempt failed
                            AWSErrorHandler.handle_aws_error(e, func.__name__)
                            raise
                        
                        if not AWSErrorHandler.handle_aws_error(e, func.__name__):
                            # Permanent error, don't retry
                            raise
                        
                        # Wait before retry with exponential backoff
                        wait_time = delay * (2 ** attempt)
                        print(f"  → Waiting {wait_time:.1f} seconds before retry {attempt + 1}/{max_retries}...")
                        time.sleep(wait_time)
                    except (NoCredentialsError, EndpointConnectionError, ConnectTimeoutError) as e:
                        print(f"Network/Credential error during {func.__name__}: {e}")
                        if attempt == max_retries:
                            raise
                        
                        wait_time = delay * (2 ** attempt)
                        print(f"  → Waiting {wait_time:.1f} seconds before retry {attempt + 1}/{max_retries}...")
                        time.sleep(wait_time)
                
                # Should never reach here, but just in case
                if last_error:
                    raise last_error
                    
            return wrapper
        return decorator


class IncludeLoader(yaml.SafeLoader):
    """YAML loader that supports !include directive for external files."""

    def __init__(self, stream):
        try:
            self._root = os.path.split(stream.name)[0]
        except AttributeError:
            self._root = os.path.curdir
        super().__init__(stream)

    def include(self, node):
        """Handle !include directive in YAML files."""
        filename = self.construct_scalar(node)

        # Support both relative and absolute paths
        if not os.path.isabs(filename):
            filename = os.path.join(self._root, filename)

        try:
            with open(filename, 'r') as f:
                return f.read()
        except FileNotFoundError:
            print(f"Warning: Include file not found: {filename}")
            return f"# Include file not found: {filename}"
        except Exception as e:
            print(f"Warning: Error reading include file {filename}: {e}")
            return f"# Error reading include file: {filename}"

# Register the include constructor
IncludeLoader.add_constructor('!include', IncludeLoader.include)


class SpotPriceManager:
    """Manages spot pricing queries and capacity scores."""

    def __init__(self, ec2_client, region: str):
        """Initialize spot price manager.

        Args:
            ec2_client: Boto3 EC2 client
            region: AWS region name
        """
        self.ec2_client = ec2_client
        self.region = region

    @AWSErrorHandler.retry_on_aws_error(max_retries=3, delay=2.0)
    def get_prices(self, instance_types: List[str], availability_zone: str = None) -> List[Dict]:
        """Get current spot prices for specified instance types.

        Args:
            instance_types: List of instance types to query (e.g., ['c7i.4xlarge'])
            availability_zone: Specific AZ to query (optional)

        Returns:
            List of dicts with instance_type, availability_zone, spot_price, timestamp
        """
        try:
            params = {
                'InstanceTypes': instance_types,
                'ProductDescriptions': ['Linux/UNIX'],
                'MaxResults': 100
            }

            if availability_zone:
                params['AvailabilityZone'] = availability_zone

            response = self.ec2_client.describe_spot_price_history(**params)

            # Get only the most recent price per instance type per AZ
            latest_prices = {}
            for item in response.get('SpotPriceHistory', []):
                key = (item['InstanceType'], item['AvailabilityZone'])
                if key not in latest_prices:
                    latest_prices[key] = {
                        'instance_type': item['InstanceType'],
                        'availability_zone': item['AvailabilityZone'],
                        'spot_price': float(item['SpotPrice']),
                        'timestamp': item['Timestamp']
                    }

            return sorted(latest_prices.values(), key=lambda x: (x['instance_type'], x['availability_zone']))

        except ClientError as e:
            print(f"Error getting spot prices: {e}")
            return []

    def get_capacity_scores(self, instance_types: List[str], target_capacity: int = 5,
                            single_az: bool = True) -> Dict[str, int]:
        """Get spot placement scores for instance types across availability zones.

        The Spot placement score is 1-10, where 10 means highly likely to get capacity.

        Args:
            instance_types: List of instance types to query
            target_capacity: Target capacity (number of instances). Default 5.
            single_az: If True, get scores per AZ; if False, get regional scores

        Returns:
            Dict mapping availability_zone (or region) to score (1-10)
        """
        try:
            params = {
                'InstanceTypes': instance_types[:10],  # API limit is 10
                'TargetCapacity': target_capacity,
                'SingleAvailabilityZone': single_az,
                'RegionNames': [self.region]
            }

            response = self.ec2_client.get_spot_placement_scores(**params)

            scores = {}
            for item in response.get('SpotPlacementScores', []):
                if single_az and 'AvailabilityZoneId' in item:
                    # Map AZ ID to AZ name
                    az_id = item['AvailabilityZoneId']
                    try:
                        az_response = self.ec2_client.describe_availability_zones(
                            ZoneIds=[az_id]
                        )
                        if az_response['AvailabilityZones']:
                            az_name = az_response['AvailabilityZones'][0]['ZoneName']
                            scores[az_name] = item['Score']
                    except:
                        scores[az_id] = item['Score']
                elif not single_az and 'Region' in item:
                    scores[item['Region']] = item['Score']

            return scores

        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', '')
            if error_code == 'UnsupportedOperation':
                return {}
            return {}
        except Exception:
            return {}


class InstanceResolver:
    """Resolves instance identifiers to instance IDs across regions."""

    def __init__(self, ec2_client, region: str, regions_config: Dict, session):
        """Initialize instance resolver.

        Args:
            ec2_client: Boto3 EC2 client
            region: Current AWS region
            regions_config: Regions configuration dictionary
            session: Boto3 session for creating clients in other regions
        """
        self.ec2_client = ec2_client
        self.region = region
        self.regions_config = regions_config
        self.session = session

    def _find_in_region(self, identifier: str, include_terminated: bool = False) -> list:
        """Find instances by name in current region."""
        try:
            filters = [{'Name': 'tag:Name', 'Values': [identifier]}]
            if not include_terminated:
                filters.append({'Name': 'instance-state-name',
                               'Values': ['pending', 'running', 'stopping', 'stopped']})

            response = self.ec2_client.describe_instances(Filters=filters)
            instances = []
            for reservation in response['Reservations']:
                instances.extend(reservation['Instances'])
            return instances
        except ClientError:
            return []

    def resolve(self, identifier: str, include_terminated: bool = False) -> Optional[str]:
        """Resolve instance identifier to instance ID, searching across regions.

        Args:
            identifier: Instance name or ID
            include_terminated: If True, also search terminated instances

        Returns:
            Instance ID or None if not found. Also updates self.region and
            self.ec2_client if found in another region.
        """
        # If it looks like an instance ID, return as-is
        if identifier.startswith('i-') and len(identifier) >= 10:
            return identifier

        # Search current region first
        instances = self._find_in_region(identifier, include_terminated)
        if instances:
            return self._handle_found_instances(instances, identifier, self.region)

        # Search other configured regions
        other_regions = [r for r in self.regions_config.get('regions', {}).keys()
                        if r != self.region]

        for region in other_regions:
            try:
                other_client = self.session.client('ec2', region_name=region)
                other_resolver = InstanceResolver(other_client, region,
                                                  self.regions_config, self.session)
                instances = other_resolver._find_in_region(identifier, include_terminated)

                if instances:
                    result = self._handle_found_instances(instances, identifier, region)
                    if result:
                        # Switch to the region where instance was found
                        print(f"Found instance '{identifier}' in region {region}")
                        self.region = region
                        self.ec2_client = other_client
                    return result
            except Exception:
                continue

        print(f"No instance found with name: {identifier}")
        return None

    def _handle_found_instances(self, instances: list, identifier: str,
                                region: str) -> Optional[str]:
        """Handle search results - return ID or print error for duplicates."""
        if len(instances) == 1:
            return instances[0]['InstanceId']

        print(f"Multiple instances found with name: {identifier}")
        for inst in instances:
            print(f"  {inst['InstanceId']} ({inst['State']['Name']}) in {region}")
        print("Please use the instance ID instead.")
        return None


class SSHConfigManager:
    """Manages SSH configuration for SpotMan instances."""

    def __init__(self):
        self.ssh_dir = os.path.expanduser('~/.ssh')
        self.config_path = os.path.join(self.ssh_dir, 'spotman_config')
        self.main_config_path = os.path.join(self.ssh_dir, 'config')

    def get_config_path(self) -> str:
        """Get the path to SpotMan's SSH config file."""
        return self.config_path

    def ensure_setup(self) -> bool:
        """Ensure SSH config includes SpotMan's config file."""
        # Ensure SSH directory exists
        os.makedirs(self.ssh_dir, exist_ok=True)

        # Create SpotMan config file if it doesn't exist
        if not os.path.exists(self.config_path):
            with open(self.config_path, 'w') as f:
                f.write("# SpotMan managed SSH configurations\n\n")

        # Check if main config includes SpotMan config
        include_line = f"Include {self.config_path}"

        if os.path.exists(self.main_config_path):
            with open(self.main_config_path, 'r') as f:
                content = f.read()
            if include_line in content:
                return True

        # Add include line to main config
        try:
            existing_content = ""
            if os.path.exists(self.main_config_path):
                with open(self.main_config_path, 'r') as f:
                    existing_content = f.read()

            with open(self.main_config_path, 'w') as f:
                f.write(f"{include_line}\n\n")
                f.write(existing_content)

            print(f"Added SpotMan SSH config include to {self.main_config_path}")
            return True

        except Exception as e:
            print(f"Warning: Could not set up SSH config include: {e}")
            return False

    def host_exists(self, host_name: str) -> bool:
        """Check if SSH config entry exists for a host."""
        if not os.path.exists(self.config_path):
            return False
        try:
            with open(self.config_path, 'r') as f:
                content = f.read()
            return f"Host {host_name}" in content
        except Exception:
            return False

    def add_entry(self, host_name: str, instance_id: str, public_ip: str,
                  ssh_user: str = 'ubuntu', identity_file: str = None,
                  port_forwards: List[Dict] = None) -> bool:
        """Add SSH config entry for an instance.

        Args:
            host_name: SSH host alias
            instance_id: EC2 instance ID (for comment)
            public_ip: Instance public IP address
            ssh_user: SSH username
            identity_file: Path to SSH key file
            port_forwards: List of port forward configs [{local_port, remote_port, remote_host}]

        Returns:
            True if successful
        """
        self.ensure_setup()

        # Build SSH config entry
        lines = [
            f"# SpotMan managed entry for {host_name} ({instance_id})",
            f"Host {host_name}",
            f"    HostName {public_ip}",
            f"    User {ssh_user}",
        ]

        if identity_file:
            lines.append(f"    IdentityFile {identity_file}")

        lines.append("    StrictHostKeyChecking no")

        # Add port forwarding rules
        for forward in (port_forwards or []):
            local_port = forward.get('local_port')
            remote_port = forward.get('remote_port')
            remote_host = forward.get('remote_host', 'localhost')
            if local_port and remote_port:
                lines.append(f"    LocalForward {local_port} {remote_host}:{remote_port}")

        ssh_entry = '\n'.join(lines) + '\n'

        try:
            # Read existing config
            existing_config = ""
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r') as f:
                    existing_config = f.read()

            # Remove existing entry for this host
            filtered_lines = []
            skip_until_next_host = False

            for line in existing_config.split('\n'):
                if line.startswith('Host '):
                    skip_until_next_host = (line == f"Host {host_name}")
                    if not skip_until_next_host:
                        filtered_lines.append(line)
                elif line.startswith('# SpotMan managed entry for') and host_name in line:
                    skip_until_next_host = True
                elif not skip_until_next_host:
                    filtered_lines.append(line)

            # Add new entry
            updated_config = '\n'.join(filtered_lines).rstrip() + '\n\n' + ssh_entry

            with open(self.config_path, 'w') as f:
                f.write(updated_config)

            print(f"SSH config updated for {host_name} -> {public_ip}")
            if port_forwards:
                print(f"Port forwarding configured: {port_forwards}")
            return True

        except Exception as e:
            print(f"Error updating SSH config: {e}")
            return False


class AWSInstanceManager:
    """Manages AWS EC2 instances with application class tagging."""
    
    def __init__(self, region: str = None, profile: str = None, quiet: bool = False):
        """Initialize the AWS Instance Manager.

        Args:
            region: AWS region to use. If None, uses default region from AWS config.
            profile: AWS profile to use. If None, uses default profile.
            quiet: If True, suppress informational messages.
        """
        self.session = boto3.Session(profile_name=profile) if profile else boto3.Session()
        self.region = region or self.session.region_name or 'us-east-1'

        try:
            self.ec2_client = self.session.client('ec2', region_name=self.region)
        except Exception as e:
            print(f"Error initializing AWS clients: {e}")
            print("Please check your AWS credentials and configuration.")
            sys.exit(1)

        # Load configuration files
        self.config = self._load_config()
        self.regions_config = self._load_regions_config()

        # Initialize helper managers
        self.ssh_config = SSHConfigManager()
        self.spot_prices = SpotPriceManager(self.ec2_client, self.region)
        self.resolver = InstanceResolver(self.ec2_client, self.region,
                                         self.regions_config, self.session)

        if not quiet:
            print(f"Using AWS region: {self.region}")
    
    def _load_config(self) -> Dict:
        """Load SpotMan configuration."""
        script_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(script_dir, 'config.yaml')
        
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    return yaml.safe_load(f) or {}
            except Exception as e:
                print(f"Warning: Error loading config: {e}")
        
        return {}
    
    def _load_regions_config(self) -> Dict:
        """Load regions configuration."""
        script_dir = os.path.dirname(os.path.abspath(__file__))
        regions_path = os.path.join(script_dir, 'regions.yaml')
        
        if os.path.exists(regions_path):
            try:
                with open(regions_path, 'r') as f:
                    return yaml.safe_load(f) or {}
            except Exception as e:
                print(f"Warning: Error loading regions config: {e}")
        
        return {}
    
    def get_profile(self, profile_name: str, required: bool = False) -> Optional[Dict]:
        """Load and return a profile configuration.

        Args:
            profile_name: Name of the profile to load
            required: If True, raise FileNotFoundError when profile not found

        Returns:
            Profile configuration dictionary or None if not found (and not required)

        Raises:
            FileNotFoundError: If profile doesn't exist and required=True
        """
        script_dir = os.path.dirname(os.path.abspath(__file__))
        profile_path = os.path.join(script_dir, 'profiles', f'{profile_name}.yaml')

        if not os.path.exists(profile_path):
            if required:
                available_profiles = self.list_profiles()
                raise FileNotFoundError(
                    f"Profile '{profile_name}' not found. "
                    f"Available profiles: {', '.join(available_profiles)}"
                )
            return None

        try:
            with open(profile_path, 'r') as f:
                return yaml.load(f, Loader=IncludeLoader)
        except Exception as e:
            print(f"Error loading profile {profile_name}: {e}")
            if required:
                raise
            return None
    
    def list_profiles(self) -> List[str]:
        """List available profiles.
        
        Returns:
            List of profile names
        """
        script_dir = os.path.dirname(os.path.abspath(__file__))
        profiles_dir = os.path.join(script_dir, 'profiles')
        
        if not os.path.exists(profiles_dir):
            return []
        
        profiles = []
        for file in os.listdir(profiles_dir):
            if file.endswith('.yaml') or file.endswith('.yml'):
                profiles.append(file.rsplit('.', 1)[0])
        
        return sorted(profiles)

    def get_spot_prices(self, instance_types: List[str], availability_zone: str = None) -> List[Dict]:
        """Get current spot prices for specified instance types.

        Delegates to SpotPriceManager.
        """
        return self.spot_prices.get_prices(instance_types, availability_zone)

    def get_spot_capacity_scores(self, instance_types: List[str], target_capacity: int = 5,
                                  single_az: bool = True) -> Dict[str, int]:
        """Get spot placement scores for instance types.

        Delegates to SpotPriceManager.
        """
        return self.spot_prices.get_capacity_scores(instance_types, target_capacity, single_az)

    def _get_user_data_script(self, profile: Dict) -> Optional[str]:
        """Get user data script from profile.

        Args:
            profile: Profile configuration

        Returns:
            User data script content or None
        """
        user_data = profile.get('user_data')
        if user_data and isinstance(user_data, str):
            return user_data
        return None

    def _prepare_user_data(self, profile: Dict) -> Optional[str]:
        """Prepare final user data script with OS updates if needed.

        Args:
            profile: Profile configuration

        Returns:
            Base64-encoded user data or None
        """
        os_type = profile.get('os_type', 'ubuntu')
        update_os = profile.get('update_os', False)
        user_data = self._get_user_data_script(profile)

        final_user_data = ""
        if update_os:
            update_scripts = {
                'ubuntu': "#!/bin/bash\napt-get update && apt-get upgrade -y\n",
                'amazon-linux': "#!/bin/bash\nyum update -y\n",
                'centos': "#!/bin/bash\nyum update -y\n"
            }
            final_user_data = update_scripts.get(os_type, "")

        if user_data:
            final_user_data = user_data if not final_user_data else final_user_data + "\n" + user_data

        if final_user_data:
            return base64.b64encode(final_user_data.encode()).decode()
        return None

    def _prepare_instance_tags(self, profile: Dict, profile_name: str, instance_name: str,
                               app_class: str, spot_instance: bool, hibernation_enabled: bool) -> List[Dict]:
        """Prepare instance tags in AWS format.

        Args:
            profile: Profile configuration
            profile_name: Name of the profile
            instance_name: Name for the instance
            app_class: Application class tag
            spot_instance: Whether this is a spot instance
            hibernation_enabled: Whether hibernation is enabled

        Returns:
            Tag specifications for AWS API
        """
        tags = profile.get('tags', {}).copy()
        tags['Name'] = instance_name
        if app_class:
            tags['ApplicationClass'] = app_class

        tags['CreatedBy'] = 'spotman'
        tags['CreatedAt'] = time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())
        tags['Profile'] = profile_name
        if spot_instance:
            tags['InstanceType'] = 'spot'
        if hibernation_enabled:
            tags['HibernationEnabled'] = 'true'

        return [{'ResourceType': 'instance', 'Tags': [{'Key': k, 'Value': str(v)} for k, v in tags.items()]}]

    def _get_key_name(self, profile: Dict) -> Optional[str]:
        """Get SSH key name from profile or region config.

        Args:
            profile: Profile configuration

        Returns:
            Key name or None
        """
        key_name = profile.get('key_name')
        if not key_name and self.regions_config:
            region_config = self.regions_config.get('regions', {}).get(self.region, {})
            key_name = region_config.get('key_name') or region_config.get('default_key')
        return key_name

    def _prepare_block_device_mappings(self, profile: Dict) -> List[Dict]:
        """Prepare block device mappings for root volume.

        Args:
            profile: Profile configuration

        Returns:
            Block device mappings for AWS API
        """
        return [{
            'DeviceName': '/dev/sda1',
            'Ebs': {
                'VolumeSize': profile.get('root_volume_size', 8),
                'VolumeType': profile.get('root_volume_type', 'gp3'),
                'DeleteOnTermination': True,
                'Encrypted': profile.get('root_volume_encrypted', False)
            }
        }]

    def _prepare_spot_options(self, profile: Dict, hibernation_enabled: bool) -> Dict:
        """Prepare spot instance market options.

        Args:
            profile: Profile configuration
            hibernation_enabled: Whether hibernation is enabled

        Returns:
            Instance market options for AWS API
        """
        spot_options = {
            'SpotInstanceType': 'persistent' if hibernation_enabled else 'one-time',
            'InstanceInterruptionBehavior': 'hibernate' if hibernation_enabled else 'terminate'
        }

        spot_price = profile.get('spot_price')
        if spot_price:
            spot_options['MaxPrice'] = str(spot_price)

        return {'MarketType': 'spot', 'SpotOptions': spot_options}

    def _wait_for_instance_and_setup_ssh(self, instance_id: str, instance_name: str) -> None:
        """Wait for instance to be running and setup SSH config.

        Args:
            instance_id: EC2 instance ID
            instance_name: Instance name for SSH host alias
        """
        print("Waiting for instance to be running...")
        waiter = self.ec2_client.get_waiter('instance_running')
        try:
            waiter.wait(InstanceIds=[instance_id], WaiterConfig={'Delay': 15, 'MaxAttempts': 20})
            print("Instance is now running.")

            host_name = f"spotman-{instance_name}"
            if self._add_ssh_config_entry(instance_id, host_name):
                print(f"SSH config updated. Connect with: ssh {host_name}")

        except Exception as e:
            print(f"Warning: Error waiting for instance or updating SSH config: {e}")
            print(f"Instance {instance_id} was created but may still be starting up.")
    
    @AWSErrorHandler.retry_on_aws_error(max_retries=3, delay=2.0)
    def _get_latest_ami(self, os_type: str, ami_name_pattern: str = None) -> str:
        """Get the latest AMI ID for the specified OS type.

        Args:
            os_type: Operating system type ('ubuntu', 'amazon-linux', 'centos')
            ami_name_pattern: Custom AMI name pattern to search for

        Returns:
            AMI ID string

        Raises:
            ValueError: If OS type is not supported
        """
        if os_type not in AMI_FILTERS:
            raise ValueError(f"Unsupported OS type: {os_type}. Supported: {list(AMI_FILTERS.keys())}")

        ami_config = AMI_FILTERS[os_type]
        name_pattern = ami_name_pattern or ami_config['name_pattern']

        filters = [
            {'Name': 'name', 'Values': [name_pattern]},
            {'Name': 'owner-id', 'Values': [ami_config['owner_id']]},
            {'Name': 'state', 'Values': ['available']},
            {'Name': 'architecture', 'Values': ['x86_64']},
            {'Name': 'virtualization-type', 'Values': ['hvm']},
            {'Name': 'root-device-type', 'Values': ['ebs']}
        ]

        try:
            response = self.ec2_client.describe_images(Filters=filters)
            
            if not response['Images']:
                raise ValueError(f"No AMIs found for OS type: {os_type}")
            
            # Sort by creation date and get the latest
            latest_ami = sorted(response['Images'], key=lambda x: x['CreationDate'], reverse=True)[0]
            ami_id = latest_ami['ImageId']
            
            print(f"Using latest {os_type} AMI: {ami_id} ({latest_ami['Name']})")
            return ami_id
            
        except ClientError as e:
            print(f"Error getting latest AMI for {os_type}: {e}")
            raise
    
    def _get_default_vpc_subnet(self, availability_zone: str = None) -> Optional[str]:
        """Get the default VPC's subnet.

        Args:
            availability_zone: If specified, return a subnet in this AZ

        Returns:
            Subnet ID of the default VPC or None if not found
        """
        try:
            # Get default VPC
            vpcs = self.ec2_client.describe_vpcs(
                Filters=[{'Name': 'is-default', 'Values': ['true']}]
            )

            if not vpcs['Vpcs']:
                return None

            default_vpc_id = vpcs['Vpcs'][0]['VpcId']

            # Get subnets in default VPC
            filters = [{'Name': 'vpc-id', 'Values': [default_vpc_id]}]
            if availability_zone:
                filters.append({'Name': 'availability-zone', 'Values': [availability_zone]})

            subnets = self.ec2_client.describe_subnets(Filters=filters)

            if not subnets['Subnets']:
                return None

            # Return the first available subnet
            return subnets['Subnets'][0]['SubnetId']

        except ClientError:
            return None
    
    def _add_ssh_config_entry(self, instance_id: str, host_name: str) -> bool:
        """Add SSH config entry for a newly created instance.

        Args:
            instance_id: EC2 instance ID
            host_name: SSH host alias

        Returns:
            True if successful, False otherwise
        """
        try:
            response = self.ec2_client.describe_instances(InstanceIds=[instance_id])
            instance = response['Reservations'][0]['Instances'][0]
            public_ip = instance.get('PublicIpAddress')
            key_name = instance.get('KeyName')

            if not public_ip:
                print("Warning: Instance has no public IP address. SSH config entry not created.")
                return False

            # Get the SSH user from regions configuration
            ssh_user = 'ubuntu'
            if self.regions_config and 'regions' in self.regions_config and self.region in self.regions_config['regions']:
                region_config = self.regions_config['regions'][self.region]
                ssh_user = region_config.get('ssh_user', ssh_user)

            # Get the SSH key file path from regions configuration
            identity_file = None
            if key_name and self.regions_config and 'ssh_keys' in self.regions_config:
                ssh_keys = self.regions_config['ssh_keys']
                if key_name in ssh_keys:
                    identity_file = ssh_keys[key_name]
                else:
                    print(f"Warning: SSH key '{key_name}' not found in regions configuration.")

            # Get port forwarding configuration from profile
            port_forwards = []
            for tag in instance.get('Tags', []):
                if tag['Key'] == 'Profile':
                    profile = self.get_profile(tag['Value'])
                    if profile:
                        port_forwards = profile.get('ssh_port_forwards', [])
                    break

            return self.ssh_config.add_entry(
                host_name=host_name,
                instance_id=instance_id,
                public_ip=public_ip,
                ssh_user=ssh_user,
                identity_file=identity_file,
                port_forwards=port_forwards
            )

        except ClientError as e:
            print(f"Error getting instance details for SSH config: {e}")
            return False

    def _instance_name_exists(self, name: str) -> bool:
        """Check if an instance with the given name already exists.

        Args:
            name: Instance name to check

        Returns:
            True if an instance with this name exists (not terminated), False otherwise
        """
        try:
            filters = [
                {'Name': 'tag:Name', 'Values': [name]},
                {'Name': 'instance-state-name', 'Values': ['pending', 'running', 'stopping', 'stopped']}
            ]
            response = self.ec2_client.describe_instances(Filters=filters)

            for reservation in response['Reservations']:
                if reservation['Instances']:
                    return True
            return False
        except ClientError:
            return False

    def _resolve_instance_identifier(self, identifier: str, include_terminated: bool = False) -> Optional[str]:
        """Resolve instance identifier to instance ID, searching across regions.

        Delegates to InstanceResolver. Updates self.region and self.ec2_client
        if instance is found in another region.
        """
        result = self.resolver.resolve(identifier, include_terminated)

        # Sync region/client changes from resolver back to manager
        if self.resolver.region != self.region:
            self.region = self.resolver.region
            self.ec2_client = self.resolver.ec2_client

        return result
    
    @AWSErrorHandler.retry_on_aws_error(max_retries=3, delay=2.0)
    def create_instance(self, profile_name: str, instance_name: str, app_class: str = None,
                       spot_price: float = None, dry_run: bool = False,
                       availability_zone: str = None, spot_override: bool = None) -> Optional[str]:
        """Create a new EC2 instance based on a profile.

        Args:
            profile_name: Name of the profile to use
            instance_name: Name for the instance
            app_class: Application class tag
            spot_price: Maximum spot price (overrides profile)
            dry_run: If True, validate parameters without creating instance
            availability_zone: Specific AZ to launch in (e.g., us-east-1a)
            spot_override: If True, force spot; if False, force on-demand; if None, use profile

        Returns:
            Instance ID if successful, None otherwise
        """
        try:
            # Check for duplicate instance name
            if self._instance_name_exists(instance_name):
                print(f"Error: An instance named '{instance_name}' already exists.")
                print("Please choose a different name or terminate the existing instance first.")
                return None

            # Load profile and apply overrides
            profile = self.get_profile(profile_name, required=True)
            if spot_price is not None:
                profile['spot_price'] = spot_price

            # Determine instance configuration
            instance_type = profile.get('instance_type', 't3.micro')
            spot_instance = spot_override if spot_override is not None else profile.get('spot_instance', False)
            hibernation_enabled = profile.get('hibernation_enabled', False)

            # Get AMI
            ami_id = profile.get('ami_id')
            if not ami_id:
                ami_id = self._get_latest_ami(profile.get('os_type', 'ubuntu'), profile.get('ami_name'))

            # Get SSH key
            key_name = self._get_key_name(profile)
            if not key_name:
                print(f"Error: No SSH key configured for region {self.region}.")
                print("Please configure a key_name in the profile or in regions.yaml")
                return None

            # Get subnet if AZ specified
            subnet_id = profile.get('subnet_id')
            if not subnet_id and availability_zone:
                subnet_id = self._get_default_vpc_subnet(availability_zone)
                if not subnet_id:
                    print(f"Error: No subnet found in availability zone {availability_zone}.")
                    return None

            # Build run_instances parameters
            run_params = {
                'ImageId': ami_id,
                'MinCount': 1,
                'MaxCount': 1,
                'InstanceType': instance_type,
                'KeyName': key_name,
                'TagSpecifications': self._prepare_instance_tags(
                    profile, profile_name, instance_name, app_class, spot_instance, hibernation_enabled
                ),
                'BlockDeviceMappings': self._prepare_block_device_mappings(profile),
                'DryRun': dry_run
            }

            # Add optional parameters
            if profile.get('security_groups'):
                run_params['SecurityGroups'] = profile['security_groups']
            if subnet_id:
                run_params['SubnetId'] = subnet_id
            if availability_zone:
                run_params['Placement'] = {'AvailabilityZone': availability_zone}

            encoded_user_data = self._prepare_user_data(profile)
            if encoded_user_data:
                run_params['UserData'] = encoded_user_data

            # Configure spot instance options
            if spot_instance:
                run_params['InstanceMarketOptions'] = self._prepare_spot_options(profile, hibernation_enabled)

            # Configure hibernation
            if hibernation_enabled:
                run_params['HibernationOptions'] = {'Configured': True}

            if dry_run:
                print("Dry run successful. Instance parameters are valid.")
                return None

            # Log creation details
            self._log_instance_creation(instance_name, profile_name, instance_type, ami_id,
                                        availability_zone, spot_instance, hibernation_enabled,
                                        app_class, profile.get('spot_price'))

            # Create the instance
            response = self.ec2_client.run_instances(**run_params)
            instance_id = response['Instances'][0]['InstanceId']
            print(f"Instance created successfully: {instance_id}")

            # Wait and setup SSH
            self._wait_for_instance_and_setup_ssh(instance_id, instance_name)
            return instance_id

        except ClientError as e:
            if e.response['Error']['Code'] == 'DryRunOperation':
                print("Dry run successful. Instance parameters are valid.")
                return None
            print(f"Error creating instance: {e}")
            return None
        except Exception as e:
            print(f"Unexpected error creating instance: {e}")
            return None

    def _log_instance_creation(self, instance_name: str, profile_name: str, instance_type: str,
                               ami_id: str, availability_zone: str, spot_instance: bool,
                               hibernation_enabled: bool, app_class: str, spot_price: float) -> None:
        """Log instance creation details."""
        print(f"Creating instance: {instance_name}")
        print(f"  Profile: {profile_name}")
        print(f"  Instance Type: {instance_type}")
        print(f"  AMI: {ami_id}")
        if availability_zone:
            print(f"  Availability Zone: {availability_zone}")
        print(f"  Spot Instance: {spot_instance}")
        if spot_instance:
            if spot_price:
                print(f"  Max Spot Price: ${spot_price}/hour")
            else:
                print(f"  Max Spot Price: on-demand (no limit)")
        print(f"  Hibernation: {hibernation_enabled}")
        print(f"  Application Class: {app_class or 'None'}")
    
    @AWSErrorHandler.retry_on_aws_error(max_retries=2, delay=1.0)
    def list_instances(self, app_class: str = None, state: str = None, 
                      profile_name: str = None, all_instances: bool = False) -> List[Dict]:
        """List EC2 instances with optional filtering.
        
        Args:
            app_class: Filter by application class
            state: Filter by instance state
            profile_name: Filter by profile name
            all_instances: If True, show all instances, not just spotman-created ones
            
        Returns:
            List of instance dictionaries
        """
        try:
            filters = []
            
            if app_class:
                filters.append({'Name': 'tag:ApplicationClass', 'Values': [app_class]})
            if state:
                filters.append({'Name': 'instance-state-name', 'Values': [state]})
            if profile_name:
                filters.append({'Name': 'tag:Profile', 'Values': [profile_name]})
            
            # Only filter for spotman instances if not showing all instances
            if not all_instances:
                filters.append({'Name': 'tag:CreatedBy', 'Values': ['spotman']})
            
            response = self.ec2_client.describe_instances(Filters=filters)
            
            instances = []
            for reservation in response['Reservations']:
                for instance in reservation['Instances']:
                    # Extract relevant information
                    instance_info = {
                        'InstanceId': instance['InstanceId'],
                        'Name': 'N/A',
                        'State': instance['State']['Name'],
                        'InstanceType': instance['InstanceType'],
                        'PublicIpAddress': instance.get('PublicIpAddress', 'N/A'),
                        'PrivateIpAddress': instance.get('PrivateIpAddress', 'N/A'),
                        'LaunchTime': instance['LaunchTime'],
                        'ApplicationClass': 'N/A',
                        'Profile': 'N/A',
                        'SpotInstance': 'spot' in instance.get('InstanceLifecycle', ''),
                        'HibernationEnabled': False
                    }
                    
                    # Extract tags
                    for tag in instance.get('Tags', []):
                        if tag['Key'] == 'Name':
                            instance_info['Name'] = tag['Value']
                        elif tag['Key'] == 'ApplicationClass':
                            instance_info['ApplicationClass'] = tag['Value']
                        elif tag['Key'] == 'Profile':
                            instance_info['Profile'] = tag['Value']
                        elif tag['Key'] == 'HibernationEnabled':
                            instance_info['HibernationEnabled'] = tag['Value'].lower() == 'true'
                    
                    instances.append(instance_info)
            
            # Sort by launch time (newest first)
            instances.sort(key=lambda x: x['LaunchTime'], reverse=True)
            return instances
            
        except ClientError as e:
            print(f"Error listing instances: {e}")
            return []
    
    def _simple_instance_action(self, instance_identifier: str, action: str,
                                 ec2_method: str, **kwargs) -> bool:
        """Execute a simple instance action (start/stop).

        Args:
            instance_identifier: Instance name or ID
            action: Action name for logging (e.g., "Starting", "Stopping")
            ec2_method: EC2 client method name to call
            **kwargs: Additional arguments for the EC2 method

        Returns:
            True if successful, False otherwise
        """
        instance_id = self._resolve_instance_identifier(instance_identifier)
        if not instance_id:
            return False

        try:
            print(f"{action} instance: {instance_identifier} ({instance_id})")
            method = getattr(self.ec2_client, ec2_method)
            method(InstanceIds=[instance_id], **kwargs)
            print(f"✅ {action.rstrip('ing')} request sent successfully.")
            return True
        except ClientError as e:
            print(f"Error {action.lower()} instance: {e}")
            return False

    @AWSErrorHandler.retry_on_aws_error(max_retries=3, delay=2.0)
    def stop_instance(self, instance_identifier: str) -> bool:
        """Stop an EC2 instance."""
        return self._simple_instance_action(instance_identifier, "Stopping", "stop_instances")

    @AWSErrorHandler.retry_on_aws_error(max_retries=3, delay=2.0)
    def start_instance(self, instance_identifier: str) -> bool:
        """Start an EC2 instance."""
        return self._simple_instance_action(instance_identifier, "Starting", "start_instances")

    @AWSErrorHandler.retry_on_aws_error(max_retries=3, delay=2.0)
    def terminate_instance(self, instance_identifier: str) -> bool:
        """Terminate an EC2 instance and cancel any associated spot request."""
        instance_id = self._resolve_instance_identifier(instance_identifier)
        if not instance_id:
            return False

        try:
            response = self.ec2_client.describe_instances(InstanceIds=[instance_id])
            instance = response['Reservations'][0]['Instances'][0]

            # Cancel spot request if present
            spot_request_id = instance.get('SpotInstanceRequestId')
            if spot_request_id:
                print(f"Cancelling spot request: {spot_request_id}")
                try:
                    self.ec2_client.cancel_spot_instance_requests(
                        SpotInstanceRequestIds=[spot_request_id]
                    )
                    print("✅ Spot request cancelled.")
                except ClientError as e:
                    print(f"Warning: Could not cancel spot request: {e}")

            print(f"Terminating instance: {instance_identifier} ({instance_id})")
            print("⚠️  This action cannot be undone!")
            self.ec2_client.terminate_instances(InstanceIds=[instance_id])
            print("✅ Termination request sent successfully.")
            return True
        except ClientError as e:
            print(f"Error terminating instance: {e}")
            return False

    @AWSErrorHandler.retry_on_aws_error(max_retries=3, delay=2.0)
    def hibernate_instance(self, instance_identifier: str) -> bool:
        """Hibernate an EC2 instance."""
        instance_id = self._resolve_instance_identifier(instance_identifier)
        if not instance_id:
            return False

        try:
            response = self.ec2_client.describe_instances(InstanceIds=[instance_id])
            instance = response['Reservations'][0]['Instances'][0]

            if not instance.get('HibernateOptions', {}).get('Configured', False):
                print("Error: Hibernation is not enabled for this instance.")
                return False

            if instance['State']['Name'] != 'running':
                print(f"Error: Instance is not running (current state: {instance['State']['Name']}).")
                return False

            print(f"Hibernating instance: {instance_identifier} ({instance_id})")
            self.ec2_client.stop_instances(InstanceIds=[instance_id], Hibernate=True)
            print("✅ Hibernation request sent successfully.")
            print("💡 Instance state and memory will be preserved.")
            return True
        except ClientError as e:
            if e.response.get('Error', {}).get('Code') == 'UnsupportedOperation':
                print("Error: Hibernation is not supported for this instance type.")
            else:
                print(f"Error hibernating instance: {e}")
            return False

    @AWSErrorHandler.retry_on_aws_error(max_retries=3, delay=2.0)
    def resume_hibernated_instance(self, instance_identifier: str) -> bool:
        """Resume a hibernated EC2 instance."""
        instance_id = self._resolve_instance_identifier(instance_identifier)
        if not instance_id:
            return False

        try:
            response = self.ec2_client.describe_instances(InstanceIds=[instance_id])
            current_state = response['Reservations'][0]['Instances'][0]['State']['Name']

            if current_state == 'running':
                print(f"Instance {instance_identifier} is already running.")
                return True
            if current_state != 'stopped':
                print(f"Error: Instance is not stopped (current state: {current_state}).")
                return False

            print(f"Resuming instance: {instance_identifier} ({instance_id})")
            self.ec2_client.start_instances(InstanceIds=[instance_id])
            print("✅ Resume request sent successfully.")
            print("💡 Instance will restore from hibernated state.")
            return True
        except ClientError as e:
            print(f"Error resuming instance: {e}")
            return False

    def check_hibernation_status(self, instance_identifier: str) -> None:
        """Check and display hibernation status of an instance.
        
        Args:
            instance_identifier: Instance name or ID
        """
        instance_id = self._resolve_instance_identifier(instance_identifier)
        if not instance_id:
            return
        
        try:
            response = self.ec2_client.describe_instances(InstanceIds=[instance_id])
            instance = response['Reservations'][0]['Instances'][0]
            
            hibernation_options = instance.get('HibernateOptions', {})
            hibernation_enabled = hibernation_options.get('Configured', False)
            current_state = instance['State']['Name']
            state_reason = instance['StateReason']['Message']
            
            print(f"\nHibernation Status for {instance_identifier}:")
            print(f"  Instance ID: {instance_id}")
            print(f"  Hibernation Enabled: {'✅ Yes' if hibernation_enabled else '❌ No'}")
            print(f"  Current State: {current_state}")
            print(f"  State Reason: {state_reason}")
            
            if hibernation_enabled:
                if current_state == 'stopped' and 'hibernation' in state_reason.lower():
                    print("  Status: 🛏️  Instance is hibernated")
                    print("  💡 Use 'resume' command to restore from hibernation")
                elif current_state == 'running':
                    print("  Status: 🟢 Instance is running")
                    print("  💡 Use 'hibernate' command to hibernate this instance")
                elif current_state == 'stopped':
                    print("  Status: 🔴 Instance is stopped (not hibernated)")
                    print("  💡 Use 'start' command to start normally")
                else:
                    print(f"  Status: 🟡 Instance is in {current_state} state")
            else:
                print("  💡 To enable hibernation, use a profile with 'hibernation_enabled: true'")
            
        except ClientError as e:
            print(f"Error checking hibernation status: {e}")

    def get_spot_instance_status(self, instance_identifier: str) -> None:
        """Get spot instance status and interruption information.

        Args:
            instance_identifier: Instance name or ID
        """
        instance_id = self._resolve_instance_identifier(instance_identifier, include_terminated=True)
        if not instance_id:
            return

        try:
            # Get instance details
            response = self.ec2_client.describe_instances(InstanceIds=[instance_id])
            instance = response['Reservations'][0]['Instances'][0]

            instance_type = instance.get('InstanceType', 'N/A')
            current_state = instance['State']['Name']
            lifecycle = instance.get('InstanceLifecycle', 'on-demand')
            spot_instance_request_id = instance.get('SpotInstanceRequestId')

            print(f"\nSpot Instance Status for {instance_identifier}:")
            print(f"  Instance ID: {instance_id}")
            print(f"  Instance Type: {instance_type}")
            print(f"  Current State: {current_state}")
            print(f"  Lifecycle: {lifecycle}")

            # Get state reason if available
            state_reason = instance.get('StateReason', {})
            if state_reason:
                print(f"  State Reason: {state_reason.get('Code', 'N/A')} - {state_reason.get('Message', 'N/A')}")

            if lifecycle != 'spot':
                print("\n  ℹ️  This is not a spot instance.")
                return

            if not spot_instance_request_id:
                print("\n  ⚠️  No spot instance request ID found.")
                return

            print(f"  Spot Request ID: {spot_instance_request_id}")

            # Get spot instance request details
            spot_response = self.ec2_client.describe_spot_instance_requests(
                SpotInstanceRequestIds=[spot_instance_request_id]
            )

            if spot_response['SpotInstanceRequests']:
                spot_request = spot_response['SpotInstanceRequests'][0]
                spot_state = spot_request.get('State', 'N/A')
                spot_status = spot_request.get('Status', {})
                spot_price = spot_request.get('SpotPrice', 'N/A')
                spot_type = spot_request.get('Type', 'N/A')

                print(f"\nSpot Request Details:")
                print(f"  Request State: {spot_state}")
                print(f"  Status Code: {spot_status.get('Code', 'N/A')}")
                print(f"  Status Message: {spot_status.get('Message', 'N/A')}")
                print(f"  Max Price: ${spot_price}/hr")
                print(f"  Request Type: {spot_type}")

                # Check for interruption behavior
                instance_interruption = spot_request.get('InstanceInterruptionBehavior', 'terminate')
                print(f"  Interruption Behavior: {instance_interruption}")

                # Interpret status using lookup table
                status_code = spot_status.get('Code', '')
                print(f"\nInterpretation:")
                if status_code in SPOT_STATUS_MESSAGES:
                    icon, message = SPOT_STATUS_MESSAGES[status_code]
                    print(f"  {icon} {message}")
                elif 'bad-parameters' in status_code:
                    print("  ❌ Bad parameters in spot request")
                else:
                    print(f"  ℹ️  Status: {status_code}")

        except ClientError as e:
            print(f"Error getting spot instance status: {e}")

    def update_ssh_config(self, instance_id: str = None, profile_name: str = None, app_class: str = None):
        """Update SSH configuration for instances.
        
        Args:
            instance_id: Specific instance ID to update
            profile_name: Update instances with this profile
            app_class: Update instances with this application class
        """
        try:
            instances = []
            
            if instance_id:
                # Update specific instance
                response = self.ec2_client.describe_instances(InstanceIds=[instance_id])
                if response['Reservations']:
                    instances = response['Reservations'][0]['Instances']
            else:
                # Build filters
                filters = [
                    {'Name': 'instance-state-name', 'Values': ['running']},
                    {'Name': 'tag:CreatedBy', 'Values': ['spotman']}
                ]
                
                if profile_name:
                    filters.append({'Name': 'tag:Profile', 'Values': [profile_name]})
                if app_class:
                    filters.append({'Name': 'tag:ApplicationClass', 'Values': [app_class]})
                
                # Get all matching instances
                response = self.ec2_client.describe_instances(Filters=filters)
                for reservation in response['Reservations']:
                    instances.extend(reservation['Instances'])
            
            if not instances:
                print("No running instances found matching the criteria.")
                return
            
            print(f"Updating SSH config for {len(instances)} instance(s)...")
            
            for instance in instances:
                instance_id = instance['InstanceId']
                instance_name = 'unknown'
                
                # Get instance name from tags
                for tag in instance.get('Tags', []):
                    if tag['Key'] == 'Name':
                        instance_name = tag['Value']
                        break
                
                host_name = f"spotman-{instance_name}"
                self._add_ssh_config_entry(instance_id, host_name)
                
        except Exception as e:
            print(f"Error updating SSH config: {e}")