# TA notes — Lab 2-7

Read the repo-root `AGENTS.md` first.

## What this lab actually teaches

> **Progressive disclosure is the same shape as retrieval, with one decisive
> difference: the model does the filtering.** Measured: `progressive` reached the
> correct answer on 55% of `all_loaded`'s context, loading exactly one document.

And the connection that makes it worth doing after chapters 3 and 4:

> **It repairs lab 4-2's failure.** There, BM25 ranked the correct tool 9th with a
> cutoff of 8 and the model never saw it. Progressive disclosure can't fail that way,
> because the model won't filter away what it knows it needs — at the cost of one extra
> round trip.

## Make them read `metadata_only`'s refusal

It declines and explains that it can't see the spec and any guess could break the call.
That's what **proves the information genuinely isn't in the context**, which is what
makes `progressive`'s success meaningful (it fetched, rather than already knowing).

## Exercise 1 is the real lesson

Vaguing pptx's metadata usually stops the model loading it at all. Only layer 1 is
permanently in context, so **only layer 1 determines whether loading happens.**
Progressive disclosure converts a retrieval-quality problem into a **description-quality**
problem — tying straight back to lab 4-1.

Note the failure mode is more insidious than 4-1's: not a wrong argument, but **never
making the call.**

## Be upfront about scale

Total content is ~1200 tokens, so the gap is only ~1.8×. Real Skill libraries are orders
of magnitude larger, where `all_loaded` stops being possible at all. Say this before a
learner concludes "only 45% saved, not worth it". Exercise 2 scales it up.

## Expected results and variance

Measured 2026-07-29: all_loaded 1920 chars / correct; metadata_only 452 / wrong;
progressive 1053 / 1 load / correct. Progressive went straight to `pptx/detail`, skipping
the md layer — it may load md first on other runs; judge the final answer, not the path.

## Language

Chinese learners: `README.zh-CN.md` / `SOLUTION.zh-CN.md`.
For English program output: `LANG = "en"` at the top of `agent.py`.
