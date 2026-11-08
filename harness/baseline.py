"""Pinned upstream mini-SWE-agent, with transport/containment instrumentation.

The DefaultAgent loop, text action parser, prompts, observation formatting,
format-error retries, and submission detection remain upstream code.
"""
import platform

from .client import HarnessError


def run_baseline(task, client, sandbox, trace, steps, output_dir):
    import litellm
    import yaml
    from minisweagent import package_dir
    from minisweagent.agents.default import DefaultAgent
    from minisweagent.environments.local import LocalEnvironment
    from minisweagent.models.litellm_textbased_model import LitellmTextbasedModel

    config = yaml.safe_load((package_dir / "config/default.yaml").read_text())

    class MeasuredModel(LitellmTextbasedModel):
        abort_exceptions = LitellmTextbasedModel.abort_exceptions + [HarnessError]

        def _query(self, messages, **kwargs):
            return litellm.ModelResponse(**client.query(messages))

        def _calculate_cost(self, response):
            # Cost is not measured; do not pretend the local token count is a
            # dollar price. Upstream needs a numeric field for its disabled cap.
            return {"cost": 0.0}

    class ContainedEnvironment(LocalEnvironment):
        def execute(self, action, cwd="", *, timeout=None):
            result = sandbox.run(action.get("command", ""), timeout=timeout or 12)
            self._check_finished(result)
            return result

        def get_template_vars(self, **kwargs):
            # Never expose the host environment (and potential API keys) to a
            # prompt template or an upstream serialized configuration.
            return {**self.config.model_dump(), **platform.uname()._asdict(), **kwargs}

    model = MeasuredModel(model_name=client.config.model, **config["model"])
    env = ContainedEnvironment(cwd=str(sandbox.work), timeout=12)
    agent = DefaultAgent(model, env, **(config["agent"] | {
        "step_limit": steps, "cost_limit": 0,
        "max_consecutive_format_errors": 3,
        "output_path": output_dir / "upstream-trajectory.json",
    }))
    try:
        outcome = agent.run(task)
    finally:
        for message in agent.messages:
            if message.get("extra", {}).get("interrupt_type") == "FormatError":
                trace.emit("parse_error", error=message.get("content"), source="upstream")
    return outcome.get("exit_status", "unknown")
