# SpotMan - Enhanced AWS Instance Manager

```
spotman/
├── spotman                     # Main CLI frontend script
├── ollama-manager             # Specialized Ollama LLM server manager
├── spotman_core.py            # Core AWS functionality library
├── regions.yaml               # Region-specific configuration (if exists)
├── requirements.txt            # Python dependencies
├── setup.sh                   # Setup script
├── README.md                  # Comprehensive documentation
├── HIBERNATION.md             # Hibernation feature guide
├── profiles/                  # Instance profile templates with native includes
│   ├── web-server.yaml        # Web server application profile
│   ├── ollama-spot.yaml       # Ollama LLM server with hibernation
│   ├── test.yaml             # Minimal test profile
│   ├── spot-hibernation.yaml # Spot instance with hibernation support
│   └── hibernation-ondemand.yaml # On-demand hibernation for production
└── scripts/                   # External scripts for modular architecture
    ├── hibernation-setup.sh   # Comprehensive hibernation configuration
    ├── ollama-setup.sh        # Complete Ollama LLM server setup
    ├── webserver-setup.sh     # Complete web server setup
    ├── test-setup.sh          # Basic test environment
    └── README.md              # Script documentation
```

## Quick Start

1. **Setup:**
   ```bash
   ./setup.sh
   ```

2. **Configure AWS credentials:**
   ```bash
   aws configure
   ```

3. **Edit configuration files:**
   - Update `regions.yaml` with your AMI IDs, key pairs, and network settings
   - Modify application profiles in `profiles/` directory as needed

4. **Set default region (optional):**
   ```bash
   ./spotman region set us-west-2
   ```

5. **Create an instance:**
   ```bash
   ./spotman create --profile test --name test01 --class test
   ```

6. **Create hibernation-enabled instances:**
   ```bash
   # Cost-optimized spot with hibernation
   ./spotman create --profile spot-hibernation --name dev-work --class development
   
   # Reliable on-demand hibernation
   ./spotman create --profile hibernation-ondemand --name prod-work --class production
   ```

7. **Create Ollama LLM instances:**
   ```bash
   # Create Ollama instance with automatic setup
   ./ollama-manager create --name ollama01
   
   # Create with custom instance type
   ./ollama-manager create --name ollama-gpu --type g5.xlarge
   ```

8. **List instances:**
   ```bash
   ./spotman list
   ./ollama-manager list
   ```

8. **Hibernation operations:**
   ```bash
   # Hibernate for cost savings
   ./spotman hibernate start dev-work
   
   # Resume when needed
   ./spotman hibernate resume dev-work
   
   # List hibernated instances
   ./spotman list --hibernated
   ```

## Key Features Implemented

✅ **Native YAML Includes** - Modular profiles using `!include` directives  
✅ **Hibernation Support** - Full hibernation for spot and on-demand instances  
✅ **Modern Spot Integration** - InstanceMarketOptions API with hibernation  
✅ **Instance Creation from YAML profiles**  
✅ **External region configuration**  
✅ **Application-focused profiles**  
✅ **Smart region defaults (remembers last used)**  
✅ **Cost optimization features**  
✅ **Application class tagging**  
✅ **Automatic OS updates during launch**  
✅ **Instance listing with filtering**  
✅ **SSH config management**  
✅ **Instance stop/terminate/hibernate/resume operations**  
✅ **AWS CLI-style command interface**  
✅ **JSON output support**  
✅ **Multiple instance profiles**  
✅ **Comprehensive error handling**  
✅ **Enhanced hibernation state management**

## Before First Use

### Configure regions.yaml:
Update the region-specific settings:
- `ami_id`: Use AMI IDs valid for each region
- `key_name`: Your EC2 key pair name for each region  
- `default_security_group_ids`: Your default security group IDs for each region
- `default_subnet_id`: Your default subnet ID for each region

### Configure application profiles:
The profiles in `profiles/` directory can be used as-is or customized:
- Modify instance types, user data scripts, tags as needed
- Add security group or subnet overrides if required
