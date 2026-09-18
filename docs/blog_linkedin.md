# LinkedIn post

Two coding agents close the same ticket. Both go green. One read three
files and stopped; the other re-read the same file eleven times, wandered
into four unrelated modules, ran `git checkout --` on uncommitted work,
and finished at twice the token cost.

Your benchmark scores them identically. Your API bill does not.

We built DSM-AE, a diagnostic framework for what actually happens inside
an agent run, and benchmarked **21 models** including **gpt-6-astra**
(plus Claude, Gemini, DeepSeek, Qwen, GLM, Grok, Pangu) across **158
behavioural patterns** and **107 deterministic metrics**. Every metric is
a deterministic check on the trajectory, not a model grading another
model.

**The headline result: we reproduced an execution-based data filter
without executing anything.**

The DeNovoSWE team released 34,816 raw agent trajectories and the 11,463
they kept after rebuilding every repository and running its test suite.
We ranked the same trajectories purely on behavioural shape — sprawl,
repeated edits, missing verification — and kept the same number.

→ **74.5% agreement** with their keep/discard decisions, on held-out data,
against a 59.3% base rate
→ **Half their quality gain**, recovered with zero sandboxes, zero
containers, zero test runs
→ Milliseconds per trajectory, on a laptop

If you are filtering agent trajectories for training data, that is a
prefilter you can run before paying for compute — and the only filter
available at all when trajectories arrive without a runnable environment.

Other findings from the study:

📊 Among runs that **all succeeded**, agents that re-read the same file
burned **1.74× the tokens**, and scope-creeping agents edited **11 files
where 3 would do**. Correctness-only benchmarks score these identically
to a clean run.

🔍 In 75 hand-read sessions of real engineering work: one agent requested
permission for the same command **185 times** without ever telling the
user it was blocked. Another spent **1,337 requests over 51 hours**
polling a background job. That task succeeded — at roughly 200× the
necessary cost.

⚠️ And the uncomfortable one, about our own battery: **81% of our gates
returned an identical value across three checkpoints of the same model.**
Almost all of it was ceiling effect, not missing signal — the items were
too easy, not the instrument too blunt. We published that, the negative
results, and the experiments that failed.

🔄 Then the useful correction: we had retired 18 tests as "too easy."
Re-running them against **gpt-6-astra** brought **8 of the 18 back** —
several failing outright. A newer, stronger model made them *harder*, not
easier. Flatness is a statement about the models you compared, not a
property of the test.

The full write-up covers the metric → behaviour → task-outcome linkage,
where the pipeline from observed behaviour to regression test leaks, and
why scaffold design moves outcomes more than model choice does.

🔗 [link]

#AIAgents #LLM #MachineLearning #SoftwareEngineering #AIEvaluation
#DataQuality
