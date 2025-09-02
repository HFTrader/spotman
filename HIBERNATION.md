# SpotMan Hibernation Support

## Overview

SpotMan now supports hibernation for both on-demand and spot instances, allowing you to suspend instances while preserving memory state and reducing costs.

## Features

### ✅ What's Available

- **Hibernation on Spot Instances**: First-class hibernation support using modern InstanceMarketOptions API
- **Hibernation on On-Demand Instances**: Full hibernation support with guaranteed manual resume
- **Automatic Encryption**: Root volumes are automatically encrypted when hibernation is enabled
- **Comprehensive Setup**: Automated swap configuration and hibernation package installation
- **Memory Preservation**: Full RAM state is preserved during hibernation
- **Cost Savings**: Only pay for storage while hibernated (no compute charges)

### 🔧 Technical Implementation

- Uses `InstanceMarketOptions` instead of legacy `request_spot_instances` API
- Automatic hibernation capability detection and validation
- Enhanced error handling with spot-specific state management
- Comprehensive hibernation scripts with proper swap configuration

## Profiles

### `hibernation-ondemand.yaml`
- **Best for**: Production workloads requiring guaranteed hibernation resume
- **Instance Type**: On-demand instances
- **Resume**: ✅ Reliable manual resume capability
- **Cost**: Higher compute cost, but predictable hibernation behavior

### `spot-hibernation.yaml`
- **Best for**: Development, batch jobs, cost-sensitive workloads
- **Instance Type**: Spot instances with hibernation
- **Resume**: ⚠️ Limited manual resume due to AWS spot request constraints
- **Cost**: Significant savings with spot pricing

## Usage Examples

### Create Hibernation-Enabled Instances

```bash
# On-demand hibernation (reliable resume)
./spotman create --profile hibernation-ondemand --name prod-hibernate

# Spot hibernation (cost-optimized)
./spotman create --profile spot-hibernation --name dev-hibernate
```

### Hibernation Operations

```bash
```bash
# Hibernate an instance
./spotman hibernate start i-1234567890abcdef0

# Resume from hibernation
./spotman hibernate resume i-1234567890abcdef0

# Check hibernation status
./spotman hibernate status i-1234567890abcdef0
```
```

## Important Limitations

### Spot Instance Hibernation Constraints

⚠️ **Manual Resume Challenges**
- Hibernated spot instances may not be manually resumable
- AWS spot requests can become 'disabled' after user-initiated hibernation
- Resume attempts may fail with `IncorrectSpotRequestState` errors

⚠️ **AWS Behavior**
- AWS may automatically restart hibernated spot instances when capacity becomes available
- Spot request state transitions: `active` → `disabled` → potential `fulfilled` on AWS restart

⚠️ **Workarounds**
- Use on-demand instances for guaranteed hibernation resume
- Allow AWS to automatically restart spot instances
- Consider terminating and recreating spot instances instead of hibernation for some use cases

### General Hibernation Requirements

✅ **Instance Requirements**
- Must use hibernation-compatible instance families (M3, M4, M5, C3, C4, C5, R3, R4, R5)
- Root volume must be encrypted (automatic with hibernation)
- RAM size must not exceed 150GB
- Adequate swap space (RAM + buffer) must be configured

✅ **Operating System Support**
- Amazon Linux 2
- Ubuntu 18.04+ (recommended)
- Windows Server 2016+

## Error Handling

SpotMan provides comprehensive error handling for hibernation scenarios:

- **Capacity Issues**: Clear messages when spot capacity is unavailable
- **State Conflicts**: Detailed explanations of spot request state problems
- **Timeout Handling**: Automatic timeout detection with user guidance
- **Alternative Solutions**: Suggestions for different approaches when hibernation fails

## Best Practices

### For Production Workloads
1. Use `hibernation-ondemand` profile for reliable hibernation resume
2. Test hibernation cycles in development first
3. Monitor hibernation performance and costs
4. Have backup strategies for critical workloads

### For Development/Testing
1. Use `spot-hibernation` profile for maximum cost savings
2. Accept that manual resume may not always work
3. Allow AWS to automatically restart when needed
4. Use hibernation for long-running development tasks

### For Batch Processing
1. Consider hibernation between large processing jobs
2. Use spot instances with hibernation for cost optimization
3. Design jobs to handle potential restart delays
4. Monitor spot pricing and availability

## Advanced Configuration

### Custom Hibernation Setup

You can customize hibernation behavior by modifying the hibernation setup script:

```bash
# Edit the hibernation setup script
nano scripts/hibernation-setup.sh

# Key areas to customize:
# - Swap size calculation
# - Hibernation package selection
# - Performance tuning
# - Monitoring setup
```

### Debugging Hibernation Issues

```bash
# Check hibernation capability
aws ec2 describe-instances --instance-ids i-xxx --query 'Reservations[].Instances[].HibernationOptions'

# Monitor spot request state
aws ec2 describe-spot-instance-requests --filters Name=instance-id,Values=i-xxx

# Check hibernation logs
sudo journalctl -u systemd-hibernate
```

## FAQ

**Q: Can I hibernate any instance type?**
A: No, only hibernation-compatible instance families support hibernation. SpotMan automatically validates this.

**Q: Why can't I resume my hibernated spot instance?**
A: AWS spot requests can become disabled after hibernation. Try waiting for AWS to automatically restart, or use on-demand instances for guaranteed resume.

**Q: How much does hibernation cost?**
A: You only pay for EBS storage while hibernated (no compute charges). Spot instances provide additional savings.

**Q: How long can instances stay hibernated?**
A: Up to 60 days. AWS will automatically stop hibernated instances after this period.

**Q: Is hibernation secure?**
A: Yes, hibernation uses encrypted root volumes and preserves all security contexts.

## Support

For hibernation-related issues:
1. Check AWS region hibernation support
2. Verify instance family compatibility
3. Review spot request states for spot instances
4. Consider switching to on-demand for critical workloads
5. Monitor AWS capacity and pricing changes

The SpotMan hibernation implementation provides best-effort support for spot instances while maintaining full reliability for on-demand instances.
