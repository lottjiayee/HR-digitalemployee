"""Module 3: AI-Assisted Content Generation (md/modules/module-3-ai-content-generation.md).

Draft implementation -- summary generation with sentence-level source anchoring, interview
question generation, and red-flag detection are built; LLM provider selection and the
hallucination-rate suspension threshold are open real-world decisions (see ASSUMPTIONS.md).

md/prompt.md §2 invariant 1 is one-directional: `scoring_engine` must have zero import dependency
on this package, and no function here may construct a `Score`. Reading Module 2's `Score` for
interview-question targeting (module-3 doc's own Dependencies section) is expected and required --
see tests/test_architectural_invariants.py, which enforces the actual (one-way) constraint.
"""
