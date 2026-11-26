# Zen 5 benchmark box (AWS c8a.metal-24xl, spot)

An isolated Zen 5 machine on demand, for measurements that need one. It is rented by the hour
as a spot instance, brought to an isolated state by `spotman create`, and terminated when the
work is done. First used on 2026-11-25 for the substack article on AMD's core complex
(`~/git/substack/cpp-performance/zen-l3-ccx-ccd`, results in `results/aws/`).

Profile: [profiles/zen5-c8a-metal.yaml](profiles/zen5-c8a-metal.yaml). First-boot script:
[scripts/zen5-metal-setup.sh](scripts/zen5-metal-setup.sh). Setup steps: [spotman_setup.py](spotman_setup.py).

## The machine

| | |
|---|---|
| CPU | AMD EPYC 9R45 (Zen 5, Turin, an AWS-only part), 96 cores, one thread per core |
| Cache | 48 KB L1d and 1 MB L2 per core; 12 CCXs of 8 cores (0-7, 8-15, ... 88-95), 32 MB L3 each, 384 MB in all |
| Memory | 192 GB, 12 channels of DDR5-6400, one NUMA node |
| Clock | base 2.6 GHz, boost 4.5 GHz (`amd-pstate-epp`) |
| Idle states | `acpi_idle`: POLL, C1, C2 |
| OS | Ubuntu 26.04, kernel 7.0.0-1018-aws (AMI `ami-0c30b7300f5fb34cd`, us-east-1) |
| Price | spot about $1.10-1.30/h in us-east-1 (on demand $5.17/h); the profile caps spot at $2/h |

## After setup

- Cores 8-95 isolated: `isolcpus=managed_irq,domain`, `nohz_full`, `rcu_nocbs`, POLL only (C1 and C2 off), boost off, clock pinned at 2.6 GHz.
- Cores 0-7 (CCX 0) are housekeeping: the OS, IRQs, RCU threads, and C1/C2 left on. Run idle or sleep tests there.
- THP off, 2048 x 2 MB hugepages reserved, `perf_event_paranoid` 1, irqbalance off, g++-14 and g++-15.
- The box powers itself off 6 h after first boot, and a poweroff terminates it.

## Before you start

- The YubiKey is plugged in and unlocked (the AWS credentials come from `pass`; if they fail, run `yubikey-unlock`).
- `~/git/tests/cpu-isolation` exists on this machine. It is not in git, and setup copies it to the box.
- `~/.ssh/amz-virginia.pem` exists (the us-east-1 key in `regions.yaml`).
- Run spotman with `/data/venv/bin/python`: the script's `python3` shebang finds a Python without boto3 on the laptop.

```
alias spotman='/data/venv/bin/python ~/git/spotman/spotman'
```

## Start it

```
spotman price --profile zen5-c8a-metal
spotman create --profile zen5-c8a-metal --alias zen5 --class benchmark --az us-east-1c
```

Use the cheapest availability zone that has capacity. On 2026-11-25 us-east-1a, 1b and 1d had no
spot capacity and 1c did; an `InsufficientInstanceCapacity` error means try the next zone.

`create` takes about 10 minutes and needs nothing from you: it launches the instance, waits for
SSH, then runs the profile's setup steps (copy the isolation kit, isolate, reboot, verify). It ends
with a line like `isolated: boost=0, cpu8 max 2600000 kHz, 2048 hugepages` and the time of the 6 h
poweroff. If a step fails, fix the cause and run `spotman setup zen5`; finished steps are skipped.

`verify-isolation.sh` prints one FAIL for the irqbalance banned mask. That one is expected (see
below); every other line should be PASS.

## Use it

```
ssh spotman-zen5
```

- Keep work in `~/tmp/<project>/` on the box.
- Pin benchmarks to isolated cores with `taskset -c 8` (or the harness's own pinning). Cycles from the counter are the portable number; ns are at 2.6 GHz.
- More time: `ssh spotman-zen5 'echo $(( $(date +%s) + 3*3600 )) | sudo tee /etc/spotman-deadline'` sets the poweroff to 3 h from now.
- A boost check on a few cores: `echo 1 | sudo tee /sys/devices/system/cpu/cpufreq/boost`, then write `cpuinfo_max_freq` into those cores' `scaling_max_freq`. Put both back afterwards (boost 0, `scaling_max_freq` 2600000).
- Copy results back before you terminate: the disk is deleted with the instance.

For the core-complex article the harness runs as:

```
scp -r ~/git/substack/cpp-performance/zen-l3-ccx-ccd/experiment spotman-zen5:~/tmp/zen-l3-ccx-ccd/
ssh spotman-zen5 'cd ~/tmp/zen-l3-ccx-ccd/experiment && nohup ./run-aws.sh > run-aws.log 2>&1 < /dev/null &'
# about 15 minutes; then
scp -r 'spotman-zen5:~/tmp/zen-l3-ccx-ccd/results/aws/*' ~/git/substack/cpp-performance/zen-l3-ccx-ccd/results/aws/
```

## Stop it

```
spotman terminate zen5
```

Billing runs until the instance is terminated; the 6 h poweroff is only a backstop. Terminating
also cancels the spot request and removes the `spotman-zen5` SSH config entry.

## Why the setup looks the way it does

- **Isolation needs a reboot**, and user data runs only once, inside the instance, so the isolation runs as `setup_steps` from the laptop.
- **Ubuntu 26.04's sudo ignores `-E`.** The isolation kit's documented `eval "$(plan-isolation.py --shell)"; sudo -E bash setup-isolation.sh` silently fell back to its default plan (2 housekeeping cores, no hugepages) on the first run. The profile passes the plan with `sudo env VAR=...` instead.
- **The kit's irqbalance mask is 64-bit.** On a 96-CPU box it left cores 64-95 unbanned, and irqbalance had put IRQs on isolated cores, including the ones under test. irqbalance is disabled at first boot and any IRQ left on 8-95 is moved to 0-7; that is why `verify-isolation.sh` still reports the mask.
- **AWS reboots on metal take 3-5 minutes**, so the reboot step waits up to 20.
- **The AMI is pinned** so the kernel matches the 2026-11-25 results. If AWS retires it, delete `ami_id` from the profile and spotman takes the newest image matching `ami_name`.
