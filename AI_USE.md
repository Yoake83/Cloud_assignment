# AI use

> Edit this file so that it matches what you actually did. The marks are for honesty and for describing how you checked the output.

**Tools used**
- Claude (Anthropic), in the claude.ai chat: used to read the assignment, plan the work, and to write the first version of the
  repository (teacher prompt, shard worker, `clean.py`, training script, FastAPI service, Dockerfiles, Kubernetes manifests,
  NACL and subnet table, GitHub Actions workflow, unit tests, Makefile).
- (add any other tool you used, for example GitHub Copilot or ChatGPT, and what for)

**How I checked what the AI gave me** (tick only what you really did)
- [ ] Read every file and understood it well enough to explain it.
- [ ] Ran `make test` and `make lint`; both pass.
- [ ] Ran `python tools/nacl_sim.py network/nacl.json network/packets_sample.jsonl --check` and checked the subnet table by hand.
- [ ] Ran `make train SUBSET=50` and the full training; compared the loss curve with what I expected.
- [ ] Checked the teacher prompt and a sample of raw teacher replies by hand (the replies themselves were never edited).
- [ ] Ran every Kubernetes experiment myself; all numbers in the report come from my own runs and the files in `results/`.
- [ ] Fixed these problems the AI's code had: (write what broke and how you fixed it)

**What I did not use AI for**: (for example the handwritten reflection)
