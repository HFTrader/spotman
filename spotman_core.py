#!/usr/bin/env python3
"""
SpotMan Core - AWS EC2 Instance Management Library
Core functionality for managing AWS EC2 instances with application class tagging.
"""

import json
import os
import sys
import time
import yaml
import shutil
from typing import Dict, List, Optional, Any
import boto3
from botocore.exceptions import ClientError, NoCredentialsError, EndpointConnectionError, ConnectTimeoutError
import subprocess
import base64
import urllib.request
import re
from functools import wraps


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


class AWSInstanceManager:
    """Manages AWS EC2 instances with application class tagging."""
    
    def __init__(self, region: str = None, profile: str = None):
        """Initialize the AWS Instance Manager.
        
        Args:
            region: AWS region to use. If None, uses default region from AWS config.
            profile: AWS profile to use. If None, uses default profile.
        """
        self.session = boto3.Session(profile_name=profile) if profile else boto3.Session()
        self.region = region or self.session.region_name or 'us-east-1'
        
        try:
            self.ec2_client = self.session.client('ec2', region_name=self.region)
            self.ec2 = self.session.resource('ec2', region_name=self.region)
        except Exception as e:
            print(f"Error initializing AWS clients: {e}")
            print("Please check your AWS credentials and configuration.")
            sys.exit(1)
        
        # Load configuration files
        self.config = self._load_config()
        self.regions_config = self._load_regions_config()
        
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
    
    def get_profile(self, profile_name: str) -> Optional[Dict]:
        """Load and return a profile configuration.
        
        Args:
            profile_name: Name of the profile to load
            
        Returns:
            Profile configuration dictionary or None if not found
        """
        script_dir = os.path.dirname(os.path.abspath(__file__))
        profile_path = os.path.join(script_dir, 'profiles', f'{profile_name}.yaml')
        
        if not os.path.exists(profile_path):
            return None
        
        try:
            with open(profile_path, 'r') as f:
                return yaml.load(f, Loader=IncludeLoader)
        except Exception as e:
            print(f"Error loading profile {profile_name}: {e}")
            return None
    
    def load_profile(self, profile_name: str) -> Dict:
        """Load a profile configuration with error handling.
        
        Args:
            profile_name: Name of the profile to load
            
        Returns:
            Profile configuration dictionary
            
        Raises:
            FileNotFoundError: If profile doesn't exist
            yaml.YAMLError: If profile has invalid YAML syntax
        """
        profile = self.get_profile(profile_name)
        if profile is None:
            available_profiles = self.list_profiles()
            raise FileNotFoundError(
                f"Profile '{profile_name}' not found. "
                f"Available profiles: {', '.join(available_profiles)}"
            )
        return profile
    
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
    
    def _get_user_data_script(self, profile: Dict) -> Optional[str]:
        """Get user data script from profile.
        
        Args:
            profile: Profile configuration
            
        Returns:
            User data script content or None
        """
        user_data = profile.get('user_data')
        if not user_data:
            return None
        
        if isinstance(user_data, str):
            return user_data
        
        return None
    
    @AWSErrorHandler.retry_on_aws_error(max_retries=3, delay=2.0)
    def _get_latest_ami(self, os_type: str) -> str:
        """Get the latest AMI ID for the specified OS type.
        
        Args:
            os_type: Operating system type ('ubuntu', 'amazon-linux', 'centos', etc.)
            
        Returns:
            AMI ID string
            
        Raises:
            ValueError: If OS type is not supported
            ClientError: If AWS API call fails
        """
        # AMI filters for different OS types
        ami_filters = {
            'ubuntu': {
                'Filters': [
                    {'Name': 'name', 'Values': ['ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*']},
                    {'Name': 'owner-id', 'Values': ['099720109477']},  # Canonical
                    {'Name': 'state', 'Values': ['available']},
                    {'Name': 'architecture', 'Values': ['x86_64']},
                    {'Name': 'virtualization-type', 'Values': ['hvm']},
                    {'Name': 'root-device-type', 'Values': ['ebs']}
                ]
            },
            'amazon-linux': {
                'Filters': [
                    {'Name': 'name', 'Values': ['amzn2-ami-hvm-*-x86_64-gp2']},
                    {'Name': 'owner-id', 'Values': ['137112412989']},  # Amazon
                    {'Name': 'state', 'Values': ['available']},
                    {'Name': 'architecture', 'Values': ['x86_64']},
                    {'Name': 'virtualization-type', 'Values': ['hvm']},
                    {'Name': 'root-device-type', 'Values': ['ebs']}
                ]
            },
            'centos': {
                'Filters': [
                    {'Name': 'name', 'Values': ['CentOS Linux 7 x86_64 HVM EBS *']},
                    {'Name': 'owner-id', 'Values': ['679593333241']},  # CentOS Project
                    {'Name': 'state', 'Values': ['available']},
                    {'Name': 'architecture', 'Values': ['x86_64']},
                    {'Name': 'virtualization-type', 'Values': ['hvm']},
                    {'Name': 'root-device-type', 'Values': ['ebs']}
                ]
            }
        }
        
        if os_type not in ami_filters:
            raise ValueError(f"Unsupported OS type: {os_type}. Supported types: {list(ami_filters.keys())}")
        
        try:
            response = self.ec2_client.describe_images(**ami_filters[os_type])
            
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
    
    def _get_default_vpc_subnet(self) -> Optional[str]:
        """Get the default VPC's subnet.
        
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
            subnets = self.ec2_client.describe_subnets(
                Filters=[{'Name': 'vpc-id', 'Values': [default_vpc_id]}]
            )
            
            if not subnets['Subnets']:
                return None
            
            # Return the first available subnet
            return subnets['Subnets'][0]['SubnetId']
            
        except ClientError:
            return None
    
    def _get_spotman_ssh_config_path(self) -> str:
        """Get the path to SpotMan's SSH config file."""
        ssh_dir = os.path.expanduser('~/.ssh')
        return os.path.join(ssh_dir, 'spotman_config')
    
    def _ensure_ssh_include_setup(self) -> bool:
        """Ensure SSH config includes SpotMan's config file."""
        main_ssh_config = os.path.expanduser('~/.ssh/config')
        spotman_config_path = self._get_spotman_ssh_config_path()
        
        # Ensure SSH directory exists
        os.makedirs(os.path.dirname(main_ssh_config), exist_ok=True)
        os.makedirs(os.path.dirname(spotman_config_path), exist_ok=True)
        
        # Create SpotMan config file if it doesn't exist
        if not os.path.exists(spotman_config_path):
            with open(spotman_config_path, 'w') as f:
                f.write("# SpotMan managed SSH configurations\n\n")
        
        # Check if main config includes SpotMan config
        include_line = f"Include {spotman_config_path}"
        
        if os.path.exists(main_ssh_config):
            with open(main_ssh_config, 'r') as f:
                content = f.read()
            
            if include_line in content:
                return True
        
        # Add include line to main config
        try:
            existing_content = ""
            if os.path.exists(main_ssh_config):
                with open(main_ssh_config, 'r') as f:
                    existing_content = f.read()
            
            with open(main_ssh_config, 'w') as f:
                f.write(f"{include_line}\n\n")
                f.write(existing_content)
            
            print(f"Added SpotMan SSH config include to {main_ssh_config}")
            return True
            
        except Exception as e:
            print(f"Warning: Could not set up SSH config include: {e}")
            return False
    
    def _check_ssh_config_exists(self, host_name: str, ssh_config_path: str = None) -> bool:
        """Check if SSH config entry exists for a host."""
        if ssh_config_path is None:
            ssh_config_path = self._get_spotman_ssh_config_path()
        
        if not os.path.exists(ssh_config_path):
            return False
        
        try:
            with open(ssh_config_path, 'r') as f:
                content = f.read()
            return f"Host {host_name}" in content
        except FileNotFoundError:
            return False
        except Exception:
            return False

    def _add_ssh_config_entry(self, instance_id: str, host_name: str, ssh_config_path: str = None) -> bool:
        """Add SSH config entry for a newly created instance."""
        if not ssh_config_path:
            ssh_config_path = self._get_spotman_ssh_config_path()
        
        # Ensure SSH include setup is configured
        self._ensure_ssh_include_setup()
        
        # Get instance details
        try:
            response = self.ec2_client.describe_instances(InstanceIds=[instance_id])
            instance = response['Reservations'][0]['Instances'][0]
            public_ip = instance.get('PublicIpAddress')
            key_name = instance.get('KeyName')
            
            if not public_ip:
                print("Warning: Instance has no public IP address. SSH config entry not created.")
                return False
            
            # Get the SSH user from regions configuration
            ssh_user = 'ubuntu'  # default
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
            profile = None
            profile_name = None
            for tag in instance.get('Tags', []):
                if tag['Key'] == 'Profile':
                    profile_name = tag['Value']
                    profile = self.get_profile(profile_name)
                    break
            
            port_forwards = []
            if profile:
                port_forwards = profile.get('ssh_port_forwards', [])
            
            # Create SSH config entry with comment and port forwarding
            identity_line = f"    IdentityFile {identity_file}" if identity_file else ""
            ssh_entry_lines = [
                f"# SpotMan managed entry for {host_name} ({instance_id})",
                f"Host {host_name}",
                f"    HostName {public_ip}",
                f"    User {ssh_user}",
            ]
            
            if identity_line:
                ssh_entry_lines.append(identity_line)
            
            ssh_entry_lines.append("    StrictHostKeyChecking no")
            
            # Add port forwarding rules
            for forward in port_forwards:
                local_port = forward.get('local_port')
                remote_port = forward.get('remote_port')
                remote_host = forward.get('remote_host', 'localhost')
                
                if local_port and remote_port:
                    ssh_entry_lines.append(f"    LocalForward {local_port} {remote_host}:{remote_port}")
            
            ssh_entry = '\n'.join(ssh_entry_lines) + '\n'
            
            # Read existing config or create new
            try:
                existing_config = ""
                if os.path.exists(ssh_config_path):
                    with open(ssh_config_path, 'r') as f:
                        existing_config = f.read()
                
                # Remove existing entry for this host if it exists
                lines = existing_config.split('\n')
                filtered_lines = []
                skip_until_next_host = False
                
                for line in lines:
                    if line.startswith('Host '):
                        if line == f"Host {host_name}":
                            skip_until_next_host = True
                            continue
                        else:
                            skip_until_next_host = False
                    elif line.startswith('# SpotMan managed entry for') and host_name in line:
                        skip_until_next_host = True
                        continue
                    
                    if not skip_until_next_host:
                        filtered_lines.append(line)
                
                # Add new entry
                updated_config = '\n'.join(filtered_lines).rstrip() + '\n\n' + ssh_entry
                
                # Write updated config
                with open(ssh_config_path, 'w') as f:
                    f.write(updated_config)
                
                print(f"SSH config updated for {host_name} -> {public_ip}")
                if port_forwards:
                    print(f"Port forwarding configured: {port_forwards}")
                return True
                
            except Exception as e:
                print(f"Error updating SSH config: {e}")
                return False
                
        except ClientError as e:
            print(f"Error getting instance details for SSH config: {e}")
            return False
    
    def _resolve_instance_identifier(self, identifier: str) -> Optional[str]:
        """Resolve instance identifier to instance ID.
        
        Args:
            identifier: Instance name or ID
            
        Returns:
            Instance ID or None if not found
        """
        # If it looks like an instance ID, return as-is
        if identifier.startswith('i-') and len(identifier) >= 10:
            return identifier
        
        # Otherwise, search by name tag
        try:
            response = self.ec2_client.describe_instances(
                Filters=[
                    {'Name': 'tag:Name', 'Values': [identifier]},
                    {'Name': 'instance-state-name', 'Values': ['pending', 'running', 'stopping', 'stopped']}
                ]
            )
            
            instances = []
            for reservation in response['Reservations']:
                instances.extend(reservation['Instances'])
            
            if len(instances) == 0:
                print(f"No instance found with name: {identifier}")
                return None
            elif len(instances) > 1:
                print(f"Multiple instances found with name: {identifier}")
                for inst in instances:
                    state = inst['State']['Name']
                    print(f"  {inst['InstanceId']} ({state})")
                print("Please use the instance ID instead.")
                return None
            else:
                return instances[0]['InstanceId']
                
        except ClientError as e:
            print(f"Error resolving instance identifier: {e}")
            return None
    
    @AWSErrorHandler.retry_on_aws_error(max_retries=3, delay=2.0)
    def create_instance(self, profile_name: str, instance_name: str, app_class: str = None, 
                       spot_price: float = None, dry_run: bool = False) -> Optional[str]:
        """Create a new EC2 instance based on a profile.
        
        Args:
            profile_name: Name of the profile to use
            instance_name: Name for the instance
            app_class: Application class tag
            spot_price: Maximum spot price (overrides profile)
            dry_run: If True, validate parameters without creating instance
            
        Returns:
            Instance ID if successful, None otherwise
        """
        try:
            # Load profile
            profile = self.load_profile(profile_name)
            
            # Get configuration values with defaults
            instance_type = profile.get('instance_type', 't3.micro')
            ami_id = profile.get('ami_id')
            os_type = profile.get('os_type', 'ubuntu')
            key_name = profile.get('key_name')
            security_groups = profile.get('security_groups', [])
            subnet_id = profile.get('subnet_id')
            user_data = self._get_user_data_script(profile)
            spot_instance = profile.get('spot_instance', False)
            hibernation_enabled = profile.get('hibernation_enabled', False)
            root_volume_size = profile.get('root_volume_size', 8)
            root_volume_type = profile.get('root_volume_type', 'gp3')
            update_os = profile.get('update_os', False)
            
            # Override spot price if provided
            if spot_price is not None:
                profile['spot_price'] = spot_price
            
            # Get AMI ID if not specified
            if not ami_id:
                ami_id = self._get_latest_ami(os_type)
            
            # Get default subnet if not specified
            if not subnet_id:
                subnet_id = self._get_default_vpc_subnet()
                if not subnet_id:
                    print("Error: No subnet specified and no default VPC found.")
                    return None
            
            # Use regions config for key name if available
            if not key_name and self.regions_config:
                regions = self.regions_config.get('regions', {})
                region_config = regions.get(self.region, {})
                key_name = region_config.get('default_key_name')
            
            if not key_name:
                print("Warning: No SSH key specified. You may not be able to connect to the instance.")
            
            # Prepare block device mappings
            block_device_mappings = [
                {
                    'DeviceName': '/dev/sda1',
                    'Ebs': {
                        'VolumeSize': root_volume_size,
                        'VolumeType': root_volume_type,
                        'DeleteOnTermination': True,
                        'Encrypted': False
                    }
                }
            ]
            
            # Prepare user data with OS updates if requested
            final_user_data = ""
            if update_os:
                if os_type == 'ubuntu':
                    final_user_data += "#!/bin/bash\napt-get update && apt-get upgrade -y\n"
                elif os_type == 'amazon-linux':
                    final_user_data += "#!/bin/bash\nyum update -y\n"
                elif os_type == 'centos':
                    final_user_data += "#!/bin/bash\nyum update -y\n"
            
            if user_data:
                if not final_user_data:
                    final_user_data = user_data
                else:
                    final_user_data += "\n" + user_data
            
            # Encode user data
            encoded_user_data = None
            if final_user_data:
                encoded_user_data = base64.b64encode(final_user_data.encode()).decode()
            
            # Prepare tags
            tags = profile.get('tags', {}).copy()
            tags['Name'] = instance_name
            if app_class:
                tags['ApplicationClass'] = app_class
            
            # Add creation timestamp and metadata
            tags['CreatedBy'] = 'spotman'
            tags['CreatedAt'] = time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())
            tags['Profile'] = profile_name  # Track which profile was used
            if spot_instance:
                tags['InstanceType'] = 'spot'
            if hibernation_enabled:
                tags['HibernationEnabled'] = 'true'
            
            # Convert tags to AWS format
            tag_specifications = [
                {
                    'ResourceType': 'instance',
                    'Tags': [{'Key': k, 'Value': str(v)} for k, v in tags.items()]
                }
            ]
            
            # Prepare run instances parameters
            run_params = {
                'ImageId': ami_id,
                'MinCount': 1,
                'MaxCount': 1,
                'InstanceType': instance_type,
                'TagSpecifications': tag_specifications,
                'BlockDeviceMappings': block_device_mappings,
                'DryRun': dry_run
            }
            
            if key_name:
                run_params['KeyName'] = key_name
            if security_groups:
                run_params['SecurityGroups'] = security_groups
            if subnet_id:
                run_params['SubnetId'] = subnet_id
            if encoded_user_data:
                run_params['UserData'] = encoded_user_data
            if hibernation_enabled:
                run_params['HibernateOptions'] = {'Configured': True}
            
            # Handle spot instances
            if spot_instance:
                spot_price = profile.get('spot_price', '0.05')  # Default max price
                
                run_params['InstanceMarketOptions'] = {
                    'MarketType': 'spot',
                    'SpotOptions': {
                        'MaxPrice': str(spot_price),
                        'SpotInstanceType': 'one-time',
                        'InstanceInterruptionBehavior': 'hibernate' if hibernation_enabled else 'terminate'
                    }
                }
            
            if dry_run:
                print("Dry run successful. Instance parameters are valid.")
                return None
            
            print(f"Creating instance: {instance_name}")
            print(f"  Profile: {profile_name}")
            print(f"  Instance Type: {instance_type}")
            print(f"  AMI: {ami_id}")
            print(f"  Spot Instance: {spot_instance}")
            if spot_instance:
                print(f"  Max Spot Price: ${profile.get('spot_price', '0.05')}/hour")
            print(f"  Hibernation: {hibernation_enabled}")
            print(f"  Application Class: {app_class or 'None'}")
            
            # Create the instance
            response = self.ec2_client.run_instances(**run_params)
            instance_id = response['Instances'][0]['InstanceId']
            
            print(f"✅ Instance created successfully: {instance_id}")
            
            # Wait for instance to be in running state for SSH config
            print("Waiting for instance to be running...")
            waiter = self.ec2_client.get_waiter('instance_running')
            try:
                waiter.wait(
                    InstanceIds=[instance_id],
                    WaiterConfig={'Delay': 15, 'MaxAttempts': 20}
                )
                print("Instance is now running.")
                
                # Add SSH config entry
                host_name = f"spotman-{instance_name}"
                if self._add_ssh_config_entry(instance_id, host_name):
                    print(f"SSH config updated. Connect with: ssh {host_name}")
                
            except Exception as e:
                print(f"Warning: Error waiting for instance or updating SSH config: {e}")
                print(f"Instance {instance_id} was created but may still be starting up.")
            
            return instance_id
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'DryRunOperation':
                print("Dry run successful. Instance parameters are valid.")
                return None
            else:
                print(f"Error creating instance: {e}")
                return None
        except Exception as e:
            print(f"Unexpected error creating instance: {e}")
            return None
    
    @AWSErrorHandler.retry_on_aws_error(max_retries=2, delay=1.0)
    def list_instances(self, app_class: str = None, state: str = None, 
                      profile_name: str = None) -> List[Dict]:
        """List EC2 instances with optional filtering.
        
        Args:
            app_class: Filter by application class
            state: Filter by instance state
            profile_name: Filter by profile name
            
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
            
            # Always filter for instances created by SpotMan
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
    
    @AWSErrorHandler.retry_on_aws_error(max_retries=3, delay=2.0)
    def stop_instance(self, instance_identifier: str) -> bool:
        """Stop an EC2 instance.
        
        Args:
            instance_identifier: Instance name or ID
            
        Returns:
            True if successful, False otherwise
        """
        instance_id = self._resolve_instance_identifier(instance_identifier)
        if not instance_id:
            return False
        
        try:
            print(f"Stopping instance: {instance_identifier} ({instance_id})")
            self.ec2_client.stop_instances(InstanceIds=[instance_id])
            print("✅ Stop request sent successfully.")
            return True
        except ClientError as e:
            print(f"Error stopping instance: {e}")
            return False
    
    @AWSErrorHandler.retry_on_aws_error(max_retries=3, delay=2.0)
    def start_instance(self, instance_identifier: str) -> bool:
        """Start an EC2 instance.
        
        Args:
            instance_identifier: Instance name or ID
            
        Returns:
            True if successful, False otherwise
        """
        instance_id = self._resolve_instance_identifier(instance_identifier)
        if not instance_id:
            return False
        
        try:
            print(f"Starting instance: {instance_identifier} ({instance_id})")
            self.ec2_client.start_instances(InstanceIds=[instance_id])
            print("✅ Start request sent successfully.")
            return True
        except ClientError as e:
            print(f"Error starting instance: {e}")
            return False
    
    @AWSErrorHandler.retry_on_aws_error(max_retries=3, delay=2.0)
    def terminate_instance(self, instance_identifier: str) -> bool:
        """Terminate an EC2 instance.
        
        Args:
            instance_identifier: Instance name or ID
            
        Returns:
            True if successful, False otherwise
        """
        instance_id = self._resolve_instance_identifier(instance_identifier)
        if not instance_id:
            return False
        
        try:
            # Get instance details for confirmation
            response = self.ec2_client.describe_instances(InstanceIds=[instance_id])
            instance = response['Reservations'][0]['Instances'][0]
            instance_name = instance_identifier
            
            for tag in instance.get('Tags', []):
                if tag['Key'] == 'Name':
                    instance_name = tag['Value']
                    break
            
            print(f"Terminating instance: {instance_name} ({instance_id})")
            print("⚠️  This action cannot be undone!")
            
            self.ec2_client.terminate_instances(InstanceIds=[instance_id])
            print("✅ Termination request sent successfully.")
            return True
        except ClientError as e:
            print(f"Error terminating instance: {e}")
            return False
    
    @AWSErrorHandler.retry_on_aws_error(max_retries=3, delay=2.0)
    def hibernate_instance(self, instance_identifier: str) -> bool:
        """Hibernate an EC2 instance.
        
        Args:
            instance_identifier: Instance name or ID
            
        Returns:
            True if successful, False otherwise
        """
        instance_id = self._resolve_instance_identifier(instance_identifier)
        if not instance_id:
            return False
        
        try:
            # Check if hibernation is enabled
            response = self.ec2_client.describe_instances(InstanceIds=[instance_id])
            instance = response['Reservations'][0]['Instances'][0]
            
            hibernation_enabled = instance.get('HibernateOptions', {}).get('Configured', False)
            if not hibernation_enabled:
                print("Error: Hibernation is not enabled for this instance.")
                print("Only instances created with hibernation support can be hibernated.")
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
            error_code = e.response.get('Error', {}).get('Code', '')
            if error_code == 'UnsupportedOperation':
                print("Error: Hibernation is not supported for this instance type or configuration.")
            else:
                print(f"Error hibernating instance: {e}")
            return False
    
    @AWSErrorHandler.retry_on_aws_error(max_retries=3, delay=2.0)
    def resume_hibernated_instance(self, instance_identifier: str) -> bool:
        """Resume a hibernated EC2 instance.
        
        Args:
            instance_identifier: Instance name or ID
            
        Returns:
            True if successful, False otherwise
        """
        instance_id = self._resolve_instance_identifier(instance_identifier)
        if not instance_id:
            return False
        
        try:
            # Check current state
            response = self.ec2_client.describe_instances(InstanceIds=[instance_id])
            instance = response['Reservations'][0]['Instances'][0]
            current_state = instance['State']['Name']
            
            if current_state == 'running':
                print(f"Instance {instance_identifier} is already running.")
                return True
            elif current_state != 'stopped':
                print(f"Error: Instance is not in stopped state (current state: {current_state}).")
                print("Only stopped instances can be resumed.")
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