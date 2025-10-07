# User Configuration Directory Support

SpotMan now supports user-defined profiles and scripts stored outside the git repository. This allows you to create custom configurations without modifying the main SpotMan codebase.

## Directory Structure

By default, SpotMan creates the following directory structure in your home directory:

```
~/.spotman/
├── profiles/          # Your custom instance profiles
├── scripts/           # Your custom setup scripts
├── regions.yaml       # Your region-specific configuration
├── backups/           # SSH config backups
├── ssh_config         # SpotMan's SSH configuration
└── config.yaml        # SpotMan configuration
```

## How It Works

When SpotMan looks for profiles, scripts, or configuration files, it follows this priority order:

1. **User Config Directory First** (`~/.spotman/`) - Your custom files
2. **Git Directory Fallback** - The original SpotMan files

This means:
- You can override any profile or script by creating a file with the same name in your user config directory
- Your custom files take precedence over the default ones
- The original files remain unchanged and serve as fallbacks

## Creating Custom Profiles

1. Create a profile file in `~/.spotman/profiles/`:
   ```bash
   cp ~/.spotman/profiles/example-profile.yaml ~/.spotman/profiles/my-profile.yaml
   ```

2. Edit the profile to match your requirements:
   ```yaml
   # Example custom profile
   instance_type: "t3.large"
   spot_instance: false
   user_data: !include scripts/my-custom-setup.sh
   # ... rest of configuration
   ```

3. Use your profile:
   ```bash
   ./spotman create --profile my-profile --name myinstance
   ```

## Creating Custom Scripts

1. Create a setup script in `~/.spotman/scripts/`:
   ```bash
   cp ~/.spotman/scripts/example-setup.sh ~/.spotman/scripts/my-setup.sh
   ```

2. Edit the script to install your preferred tools and configurations

3. Reference it in your profiles:
   ```yaml
   user_data: !include scripts/my-setup.sh
   ```

## Configuring Regions

SpotMan uses `regions.yaml` to define region-specific settings like AMI IDs, key pairs, and network configurations:

1. **Automatic Setup**: If `regions.yaml` doesn't exist, SpotMan creates a sample file automatically
2. **Migration**: If you had a `regions.yaml` in the git directory, it's automatically copied to your user config
3. **Customization**: Edit `~/.spotman/regions.yaml` with your actual AWS resources

### Sample regions.yaml structure:
```yaml
# SSH Key Mappings
ssh_keys:
  my-keypair-us-east: "~/.ssh/my-keypair-us-east.pem"

regions:
  us-east-1:
    key_name: "my-keypair-us-east"
    default_security_group_ids:
      - "sg-0123456789abcdef0"
    default_subnet_id: "subnet-0123456789abcdef0"

defaults:
  instance_type: "t3.micro"
  os_type: "ubuntu"
  update_os: true
```

## Examples

### Example Profile
See `~/.spotman/profiles/example-profile.yaml` for a complete example profile that demonstrates:
- Custom instance configuration
- Reference to user scripts
- Proper tagging and documentation

### Example Script
See `~/.spotman/scripts/example-setup.sh` for a complete example setup script that demonstrates:
- System updates and package installation
- Development tool setup
- Environment configuration
- User-friendly info scripts

## Benefits

- **Customization**: Create profiles and scripts tailored to your specific needs
- **Isolation**: Keep your customizations separate from the main codebase
- **Version Control**: The main SpotMan repository remains clean
- **Flexibility**: Override any default profile or script as needed
- **Backup Safety**: Your custom files are not affected by SpotMan updates

## Migration

If you have existing custom profiles or scripts, you can:
1. Move them to `~/.spotman/profiles/` and `~/.spotman/scripts/`
2. Update any relative paths in your profiles
3. Test that everything works as expected

## Troubleshooting

- Profiles not found: Check that files are in `~/.spotman/profiles/` with `.yaml` extension
- Scripts not found: Check that scripts are in `~/.spotman/scripts/` and have execute permissions
- Include errors: Verify relative paths in your YAML files
- Permission issues: Ensure your user has read/write access to `~/.spotman/`

## Advanced Usage

You can also:
- Create subdirectories within `~/.spotman/profiles/` and `~/.spotman/scripts/`
- Use absolute paths in include directives if needed
- Share your custom profiles and scripts with team members
- Version control your `~/.spotman/` directory separately if desired
