# Running Your Own AI Coding Assistant: The Journey from Hardware Dreams to Cloud Reality

## When Good Hardware Isn't Good Enough

A developer asked me a question that I hear variations of constantly: "I've got Ubuntu 22.04 with an Intel CPU and a graphics card. What do I need to tell you so you can give me realistic expectations about running an on-premises LLM for code help like Claude?"

Let me be direct - **this question reveals a fundamental misunderstanding about what it takes to run serious language models**. It's not about having "a graphics card." It's about having the right graphics card with enough VRAM to actually load the model weights into memory while leaving room for the computations.

A trader I know at Citadel made this exact mistake last year. He grabbed an old gaming rig, saw it had an NVIDIA card, and figured he was set. The card had 4GB of VRAM. In the LLM world, that's like showing up to a Formula 1 race on a bicycle.

### The VRAM Wall You'll Hit Immediately

Here's what nobody tells you upfront: your GPU's VRAM capacity dictates everything. When you're running a language model, that VRAM holds the model weights, your input context, and all the intermediate calculations happening during inference. Run out of VRAM, and you're either swapping to system RAM (catastrophically slow) or the model simply won't load.

The developer had two machines worth examining:

**Machine 1**: RTX 2060 SUPER with 8GB VRAM, 32GB system RAM, Intel i7-10700K
**Machine 2**: AMD Threadripper 3960X with 24 cores, 64GB RAM, but an ancient AMD Radeon from 2013

The first machine is actually decent for this work. The second machine, despite that monster CPU, has a GPU so old it's basically worthless for inference. But here's where things get interesting - **that Threadripper can still run larger models purely on CPU**, just much slower.

## Let's See What Actually Runs

With 8GB of VRAM on the RTX 2060, you're in the 7B to 13B parameter range. Someone from the prop trading world told me about trying to squeeze a 70B model onto similar hardware. The thing crawled at about 2 tokens per second. That's slower than you can read. Completely unusable for actual work.

The models that work well in this range are DeepSeek Coder 6.7B, CodeLlama 13B, and the newer Qwen2.5-Coder 7B. Performance-wise, you're looking at 15-30 tokens per second. Fast enough that you're not watching individual words appear, but you'll notice the difference from cloud services immediately.

### What This Means for Real C++ Development

My former colleague at Hudson River Trading was evaluating local models for some internal tooling work. The 7B models handled basic code completion fine - explaining straightforward algorithms, simple refactoring suggestions, syntax help, boilerplate generation. Where they completely fell apart was the interesting stuff.

**Complex architectural decisions, multi-file refactoring, the kind of subtle optimization work we do in HFT** - a 7B model doesn't have enough capacity to hold the context of a large codebase while reasoning about cache line optimization simultaneously. It's like asking someone to juggle while doing calculus. Technically possible, but the results aren't pretty.

## The Ollama Path of Least Resistance

Someone at JP Morgan's quant desk mentioned they set this up for their team's weekend projects. The whole thing took about ten minutes, which honestly surprised me:

```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Pull a model
ollama pull deepseek-coder:6.7b

# Start using it
ollama run deepseek-coder:6.7b
```

The brilliant thing about Ollama is **it handles GPU configuration automatically**. No wrestling with CUDA_PATH, no debugging driver versions, no wondering if you've got the right cuDNN installed. It detects your hardware and configures itself. For developers who just want to write code instead of fighting with infrastructure, this is gold.

### Making This Actually Useful in VSCode

The Continue extension is where this gets practical for actual work. A developer showed me his workflow, and it's pretty slick. Install Continue in VSCode, it auto-detects your local Ollama installation, and suddenly you've got Ctrl+L for chat sidebar, Ctrl+I for inline code generation, and you can select code and ask questions about it.

The experience is... okay. It's not Claude. Let me be clear about that. But for quick "how do I use this STL algorithm" questions or "refactor this function to use modern C++" requests, it's fast and private. No rate limits, no sending your proprietary code to Anthropic's servers.

## The Threadripper Surprise

Now here's where the second machine gets interesting. That AMD GPU from 2013? Worthless. A Radeon HD 8570 has maybe 2GB of VRAM and zero modern inference optimization. But that CPU with its 24 cores and 64GB of RAM? Different story entirely.

A colleague mentioned running a 33B parameter model on pure CPU with a similar setup. The Threadripper's massive core count can push reasonable performance for larger models - you're looking at 5-15 tokens per second depending on model size. **Slower than GPU, but you can run much smarter models**.

### The Two-Machine Strategy Nobody Talks About

Here's what actually makes sense if you've got both machines sitting around. Use the RTX 2060 machine as your daily driver - fast 7B models for quick questions and autocomplete. Keep it local, get responses in seconds.

Use the Threadripper as your "think hard about this" server. Run 33B models when you need deeper analysis. SSH in, submit your complex question, go get coffee. I know someone who set this up, and they treat the Threadripper like having a senior developer on retainer. You don't bother them with "how do I reverse a string" but you absolutely ask them about template metaprogramming optimization strategies.

## When Cloud Becomes the Better Answer

Let's talk about AWS, because the marketing around GPU instances is mostly garbage designed to confuse you into overpaying.

A trader mentioned he looked into running Ollama on AWS instead of dealing with hardware maintenance. The math is actually compelling. **An AWS g4dn.xlarge spot instance costs about $0.16/hour**. That's $28 per month if you use it 6 hours daily.

But here's what they don't tell you in the AWS documentation: that's with spot pricing, which means AWS can reclaim your instance with 2 minutes notice when they need the capacity elsewhere. For most workloads, this sounds terrifying. For our use case? It's actually perfect.

### The Hibernation Trick That Changes Everything

You can configure spot instances to hibernate instead of terminate when interrupted. This is brilliant - your model stays loaded in RAM, the machine pauses, saves state to disk, and when capacity comes back, it resumes exactly where it left off. **No reloading 30GB models every time AWS needs your hardware back**.

Someone from Citadel's infrastructure team walked me through their math on this approach. A g5.xlarge spot in US East (Virginia) runs about $0.30/hour, so roughly $54 monthly for 6 hours daily usage. Add $10/month for the EBS storage that holds your hibernated state, and you're at $64/month total.

That gets you an NVIDIA A10G GPU with 24GB of VRAM - better than the RTX 2060 - and the ability to run 70B models. Not 7B models like you're stuck with locally. Seventy billion parameters. **The difference in code understanding and reasoning is substantial**.

## The São Paulo Question That Changed The Calculus

"Consider AWS in São Paulo though."

This one sentence changed the entire cost analysis. São Paulo (sa-east-1) has prices about 40% higher than US East. Same g5.xlarge that costs $54/month in Virginia runs $76/month in Brazil. For someone working in São Paulo, that's an extra $264 annually.

But here's what I learned from running distributed systems across regions: **the 150ms latency difference doesn't matter for LLM inference**. At all.

When you're asking the model a question and waiting 10 seconds for it to generate a response, you literally cannot perceive the difference between a 5ms round trip and a 150ms round trip. The model inference time dominates everything else so completely that network latency disappears into the noise.

A developer told me he tried both São Paulo and US East instances from his office in Brazil. In actual usage, he couldn't tell the difference. The only time latency might matter is for aggressive tab-completion where suggestions appear as you type, but even then, 300ms autocomplete delay is perfectly usable.

**Use US East (Virginia) and save the money**. Let the model think in the cloud. The latency is irrelevant.

## The Real Cost Analysis Nobody Publishes

Someone at Vitorian LLC did a comprehensive cost analysis comparing every option. Let me walk you through what things actually cost when you factor in everything, not just the advertised prices.

### Cloud AI Services You're Probably Using

Claude Pro runs $20 monthly but gives you 5x the usage of the free tier. Sounds reasonable until you realize the rate limits reset every 5 hours. A colleague told me they hit limits by Wednesday every week doing moderate coding work. Not suitable for professional use.

Claude Max has two tiers now - $100/month gets you 5x more than Pro, $200/month gets you 20x more and essentially unlimited access for most users. That's $1,200 to $2,400 annually. This is getting serious.

GitHub Copilot Pro at $10/month is honestly the best value for pure coding assistance. Unlimited code completions, 300 "premium requests" monthly for chat and advanced features, works directly in your IDE. Someone from the trading desk mentioned their entire team uses it.

The Claude API uses pay-per-use pricing - Sonnet 4.5 costs $3 per million input tokens, $15 per million output tokens. Opus 4.1 is $15 input, $75 output per million. **Hard to predict costs, but roughly $17.70/month equals Claude Pro subscription pricing**.

### Self-Hosted Reality Check

Local RTX 2060 setup costs you exactly zero for hardware you already own, plus about $15/month in electricity running 6 hours daily. Models are free. Total: $15/month for 7B-13B models at junior developer capability level.

AWS g4dn.xlarge spot in US East: $28/month for the instance plus $10/month storage, total $38/month. You get 34B models with competent mid-level developer capability.

AWS g5.xlarge spot in US East: $54/month instance plus $10/month storage, total $64/month. You get 70B models with senior developer level reasoning.

AWS g5.xlarge spot in São Paulo: $76/month instance plus $12/month storage, total $88/month. Same 70B capability, lower latency that doesn't actually matter.

## The Comparison Table You Actually Need

A developer at Hudson River Trading shared their analysis after three months using different setups. This table is based in their real experience, not marketing materials:

**GitHub Copilot Pro** ($10/month) - Best for daily coding, hits premium request limits eventually
**Claude Pro** ($20/month) - Good for general use, rate limits hit quickly with moderate usage  
**Local RTX 2060** ($15/month) - Privacy wins, limited reasoning capability
**AWS g4dn.xlarge** ($38/month) - Cost-conscious choice, older T4 GPU
**AWS g5.xlarge US** ($64/month) - Best value overall, 70B models, 150ms latency that doesn't matter
**AWS g5.xlarge BR** ($88/month) - Same capability, local latency, costs more
**Claude Max Tier 1** ($100/month) - Professional work, still has some limits
**Claude Max Tier 2** ($200/month) - Essentially unlimited, expensive

### What The Math Actually Tells You

Here's the part that surprised me. **For pure coding assistance, GitHub Copilot Pro at $10/month is unbeatable value**. It's purpose-built for coding, integrates perfectly with your IDE, and 300 premium requests monthly is enough for most developers. That's $120 annually.

For general AI assistance plus coding, Claude Pro at $20/month seems reasonable until you actually use it. Someone told me they hit rate limits within 3-4 days of moderate use. You end up rationing your usage, which defeats the entire purpose of having AI assistance.

For serious professional work, here's where it gets interesting. Claude Max Tier 1 at $100/month costs $1,200 yearly. An AWS g5.xlarge in US East running 6 hours daily costs $768 annually. **You're saving $432 per year, getting better privacy, and running larger models**.

But there's a hidden cost nobody talks about: your time. Setting up and maintaining AWS infrastructure isn't free. A trader mentioned he spent about 8 hours getting everything configured properly. If your time is worth $100/hour, that's $800 in setup cost. Suddenly Claude Max looks cheaper for the first year. After that, the AWS option wins on pure economics.

## The Strategy Most People Miss Completely

Someone from the prop trading world shared their actual setup, and it makes complete sense once you think about it:

**Daily coding**: GitHub Copilot Pro ($10/month) - integrated, fast, purpose-built  
**Complex problems**: AWS g5.xlarge ($64/month) - your own 70B model, private, no limits
**Architecture discussions**: Claude Pro ($20/month) - still the best for system design reasoning

Total: $94/month for a complete setup covering every use case.

Compare that to Claude Max Tier 2 at $200/month, which still has limits and isn't optimized specifically for coding. Or GitHub Copilot Pro+ at $39/month plus Claude Pro at $20/month ($59 total), which gives you less capability than the AWS option for coding-heavy work.

The question isn't which is cheapest. **The question is which gives you the capability you actually need without breaking your workflow**. Different tools for different jobs.

## Building the Management Script

All this analysis was great, but managing AWS instances manually is tedious enough that people just don't do it. That's when automation became necessary.

The initial requirements were simple - start instances, stop instances, check status, handle hibernation. But the real complexity emerged from a practical operations concern:

"When first creating the box, I want the script to take care of SSH configuration by adding a line to include an SSH config specific for ollama manager and then adding the given box inside that config to minimize editing the main SSH config file."

This requirement revealed someone who actually understood real-world usage patterns. The problem: each instance gets a new public IP when started, manually updating `~/.ssh/config` is annoying, using EC2 key pairs every time is tedious, and mixing ollama instances with personal SSH config creates a mess.

### The SSH Solution Nobody Implements

The script now creates `~/.ollaman/ssh_config` as a separate config file for managed instances, adds an Include directive to `~/.ssh/config` to pull in ollama configs, auto-generates host entries where each instance gets an `ollama-<instance-id>` alias, waits for SSH to become ready after launch, and runs `ssh-copy-id` using the EC2 key for initial authentication.

When instances restart with new IPs, the config auto-updates. After running `launch`, you just `ssh ollama-i-1234567890abcdef` and it works. Port forwarding for Ollama (port 11434) happens automatically.

A developer at JP Morgan told me this saved him probably 30 minutes weekly in SSH config management across multiple instances. That's 26 hours yearly. **At trading firm compensation rates, the automation pays for itself in the first month**.

## The Architecture That Emerged

The script evolved through iterative refinement, each version addressing real usage patterns, but the most significant change came from a fundamental architecture problem that nobody anticipated.

**Version 1** had basic start/stop with YAML config files. Problem: users had to manually track instance IDs and edit configs constantly.

**Version 2** embedded sensible defaults directly in the script. You could export a config file when needed, but the script worked immediately with zero configuration. Game-changer for getting started.

**Version 3** added instance tagging and discovery. All instances created by the script get tagged with `ManagedBy: ollama-manager`, and the `list` command shows all managed instances globally. You can have instances across regions and the script tracks them all.

**Version 4** implemented automated SSH configuration management. This is the version that actually gets used in production, because it removes all the friction from daily operations.

**Version 5** - The Refactoring That Fixed Everything.

### When Integration Becomes the Problem

Someone at a prop trading firm hit the exact issue that reveals the weakness in standalone scripts: "When I run ./ollama-manager I get 'No module named spotman'".

This error message tells a story. The ollama-manager wasn't just a script anymore - it had grown into a specialized tool that needed to share functionality with the broader SpotMan infrastructure management framework. The old approach of copying code between scripts was creating maintenance hell.

**The integration attempt failed because Python import systems don't work the way most people think they do**. You can't just `from spotman import AWSInstanceManager` when `spotman` is a standalone script, not a proper Python module. The exec() workarounds and namespace manipulation were getting ugly fast.

A developer at Hudson River Trading put it perfectly: "We need the ollama-manager to use the same robust AWS error handling, the same SSH configuration logic, the same instance lifecycle management. But we also need it to remain a specialized tool for Ollama workloads."

### The Modular Architecture Solution

The solution required a complete refactoring that nobody wanted to do but everyone knew was necessary:

**Extract Core Functionality**: All the AWS instance management logic moved into `spotman_core.py` - a proper Python module with classes that can be imported cleanly. No more duplicated code between tools.

**Lightweight Frontends**: The `spotman` script became a CLI frontend that imports from `spotman_core`. The `ollama-manager` became another frontend that imports the same core functionality. Same robust infrastructure, different interfaces.

**Shared Infrastructure**: SSH configuration with port forwarding, AWS error handling with exponential backoff, hibernation management, instance discovery across regions - all this lives in the core module and gets used by both tools.

The refactoring took a day but fixed fundamental architectural problems that would have gotten worse over time. Someone mentioned this pattern from microservices architecture - **shared libraries for common functionality, specialized interfaces for different use cases**.

### What The New Architecture Looks Like

```bash
spotman/
├── spotman_core.py            # Core AWS functionality library  
├── spotman                    # Main CLI frontend
├── ollama-manager            # Specialized Ollama manager
├── setup.sh                  # Enhanced setup script
└── profiles/                 # Instance configurations
```

The `spotman_core.py` module contains:
- `AWSInstanceManager` class with all EC2 operations
- `AWSErrorHandler` for robust error handling with retries
- `IncludeLoader` for YAML profile processing
- SSH configuration management with generic port forwarding
- Instance lifecycle management across all operations

Both frontends import the same core: `from spotman_core import AWSInstanceManager`. **No more "No module named" errors. No more code duplication. No more maintenance nightmare.**

### The Generic Port Forwarding Breakthrough

During the refactoring, a requirement emerged that changed everything: "I don't like having code specific to Ollama inside spotman. I'd prefer to have generic port forwarding options in the config."

This was the right architectural instinct. Hard-coding Ollama-specific logic into the core framework violated separation of concerns. The solution was elegant:

**Generic SSH Port Forwarding**: Profiles can now specify `ssh_port_forwards` sections that work for any application:

```yaml
ssh_port_forwards:
  - local_port: 11434     # Ollama API
    remote_port: 11434
    remote_host: localhost
  - local_port: 8080      # Web interface  
    remote_port: 80
    remote_host: localhost
```

The core framework reads this configuration and automatically adds LocalForward rules to SSH config. **Works for Ollama, web servers, databases, Jupyter notebooks, anything that needs port forwarding**. The ollama-manager just uses a profile with Ollama's port configured.

A developer at Citadel mentioned this approach solved their broader infrastructure problem: "We can now create profiles for our internal tools that need specific port forwarding without modifying the core framework code."

### Setup and Build Configuration That Actually Works

The refactoring revealed gaps in the installation process that nobody noticed when everything was a single script. The new modular architecture required updating:

**Enhanced Setup Script**: Now handles both `spotman` and `ollama-manager` executables, verifies `spotman_core.py` module presence, creates symlinks for both tools, runs installation verification tests, and provides comprehensive quick start instructions.

**Updated Dependencies**: Added `requests>=2.28.0` for ollama-manager API testing functionality and explicit `botocore>=1.29.0` version requirements. The automated setup properly handles all dependencies.

**Documentation Updates**: README.md and QUICKSTART.md now reflect the modular architecture, show both tools in examples, and document the new file structure.

The setup script now runs verification tests:
```bash
✅ spotman: Working correctly
✅ ollama-manager: Working correctly
```

Someone at JP Morgan told me this level of setup automation was critical for team adoption: "Developers won't use tools that require fighting with installation and imports. Everything needs to just work."

### What It Does Today

The modular architecture now provides two complementary tools that share the same robust infrastructure:

**SpotMan Core Framework**:
```bash
# List all managed instances globally  
./spotman list --class ollama --state running

# Create instances with any profile
./spotman create --profile ollama-spot --name ollama01 --class ollama

# Manage instances with hibernation
./spotman hibernate ollama01
./spotman resume ollama01

# Update SSH configs with port forwarding
./spotman update-ssh --class ollama
```

**Specialized Ollama Manager**:
```bash
# List all Ollama instances specifically
./ollama-manager list

# Launch with Ollama-optimized defaults
./ollama-manager create --name ollama01

# Test Ollama API connectivity
./ollama-manager test ollama01

# Connect with SSH port forwarding  
./ollama-manager connect ollama01

# Show Ollama service logs
./ollama-manager logs ollama01
```

The implementation uses the shared `spotman_core.py` module for AWS SDK operations, YAML config parsing, and SSH configuration management. **Both tools get the same robust error handling, the same hibernation logic, the same port forwarding capabilities**.

Native SSH tools handle agent forwarding, known hosts management, and all the edge cases that reimplementing SSH in Python gets wrong. Using subprocess to shell out to native tools is more reliable than trying to reimplement SSH.

### The Import Problem That Revealed Everything

The modular refactoring solved a Python import issue that was blocking real-world usage, but it revealed something bigger: **single-purpose scripts don't scale when you need shared infrastructure**.

Before the refactoring, adding hibernation support to ollama-manager meant copying hibernation code from spotman. Adding better error handling meant copying error handling code. Adding region support meant copying region logic. Every improvement had to be implemented twice.

After the refactoring, improvements to the core module automatically benefit both tools. When someone adds support for new instance types, both tools get it. When AWS error handling gets more sophisticated, both tools become more reliable. **Single source of truth for all infrastructure logic**.

## Why This Actually Matters for Trading Firms

At HFT firms like Hudson River Trading or Citadel, you cannot send proprietary trading algorithms to third-party APIs. It's not a preference, it's mandatory. **Self-hosted infrastructure isn't optional**.

The $64-88/month per developer is trivial compared to the risk of IP leakage. One leaked algorithm could cost millions. The script makes this infrastructure accessible to developers without requiring DevOps expertise.

Someone at Vitorian LLC uses this exact setup for HFT consulting work. When you're analyzing microsecond-level performance optimizations or designing low-latency trading strategies, you need an AI that understands the context without sending that context to Anthropic or OpenAI's servers.

The privacy aspect alone justifies the cost and complexity. Everything else - the cost savings, the larger models, the lack of rate limits - those are bonuses.

## The Daily Workflow That Actually Works

Morning routine: `python manager.py start i-<instance-id>`, wait about 30 seconds for it to resume from hibernation, SSH automatically connects via the pre-configured alias.

Work all day with Ollama via VSCode Continue, which automatically connects to localhost:11434 through the SSH tunnel. The model runs in AWS with 24GB VRAM, but from your IDE it feels completely local.

Evening routine: `python manager.py stop i-<instance-id>`, instance hibernates, you're now only paying for storage at about $10/month instead of $54/month for compute.

A developer told me this workflow became so automatic after the first week that they forgot they were even using AWS. It just felt like having a really powerful local setup that magically appeared when needed.

## Lessons From Building This

**Hardware limitations are real and nobody wants to admit it**. You can't run Claude-equivalent models on consumer hardware. A 7B model on an RTX 2060 is like having a smart intern, not a senior developer. Manage your expectations accordingly.

**Cloud latency doesn't matter for LLMs**. The 150ms versus 5ms difference is completely irrelevant when the model takes 10 seconds to generate a response. Use the cheapest region, not the closest one.

**Multi-tool strategy beats single solution**. Instead of Claude Max at $200/month, use GitHub Copilot for $10, AWS g5.xlarge for $64, and Claude Pro for $20. Total $94/month with better capabilities for each specific use case.

**Automation enables experimentation**. Without the management script, manually handling AWS spot instances, SSH configs, and IP changes would be unbearable. Automation removes friction and enables actually using the infrastructure instead of fighting with it.

**Iterative design through conversation works**. This script wasn't designed upfront with complete requirements. It evolved through usage, each requirement revealing new insights about real-world patterns. That's how good tools get built.

**Modular architecture prevents technical debt**. The biggest lesson came from the refactoring: **when you start copying code between tools, you're already in trouble**. Extracting shared functionality into a proper module made both tools more reliable and development faster.

**Generic abstractions beat specific implementations**. Making port forwarding generic instead of Ollama-specific meant the framework could support web servers, databases, and any other services that need port forwarding. Someone at Citadel uses the same framework for their internal analytics tools.

**Python import systems are more complex than they appear**. The "No module named" error taught us that exec() workarounds and namespace manipulation are signs of architectural problems. Proper modules with proper imports are worth the refactoring effort.

**Setup automation determines adoption**. Developers won't use tools that require fighting with installation issues. The enhanced setup script that verifies both tools work correctly was critical for team adoption. Installation has to be completely painless.

## Where This Goes Next

The script solves the core problem: making self-hosted LLMs practical for developers. Additional features should be driven by real usage, not speculation about what might be useful.

Potential enhancements include cost monitoring that pulls AWS billing data and shows per-instance costs, model management that auto-installs Ollama and pulls specified models, health checks that verify Ollama is running and responsive, backup and restore with EBS snapshot management, team features like shared instance pools and reservation systems, performance monitoring tracking tokens per second and model performance, and auto-scaling that launches instances on-demand and terminates when idle.

But those are future problems. Right now, the script makes it possible for any developer with an AWS account to run Claude-scale LLMs on their own infrastructure with complete privacy and control. That's the promise delivered.

---

**The code and this documentation are provided for educational and commercial use**. Modify, distribute, and use as you see fit. The goal is making powerful AI infrastructure accessible to everyone who needs it.

If you build on this work - add support for more cloud providers, implement cost monitoring dashboards, create team collaboration features, build model performance tracking - share what you build. The community benefits when we solve infrastructure problems together.

*October 2025 - Version 1.0 with SSH automation and multi-region support*