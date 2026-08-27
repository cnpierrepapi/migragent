"""The agent layer. Build 7.3, designed in docs/AGENTS.md.

One place per judgment call that today is a single unguarded model call or an
open defect. Everything deterministic stays in plain code and appears in the
pipelines as a non-LLM node, because a rule an agent can decide to skip is not
a rule.

Nothing in here is on by default. Each agent is reached through a flag, and the
rollout is lane by lane. See docs/AGENTS.md.
"""
