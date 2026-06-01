from __future__ import annotations

import subprocess
from pathlib import Path

import yaml

from hermes_slack_ext.core import secrets
from hermes_slack_ext.core import tts as T
from hermes_slack_ext.wizard.engine import Step, WizardContext
from hermes_slack_ext.wizard.prompts import Prompts


class TtsStep(Step):
    """Optional per-profile TTS setup. Default is text-only (skipped). When opted
    in, the user picks a provider and a distinct voice per profile; the step writes
    the provider API key to each profile .env, best-effort installs a built-in
    provider's SDK into the Hermes venv, and stages a per-profile ``tts`` config
    block to merge into each profile's config.yaml. The [TTS] send-hook then speaks
    a profile's wrapped text in its configured voice."""

    id = "tts"
    title = "Meeting TTS voices (optional)"

    def should_run(self, ctx: WizardContext) -> bool:
        return "meeting" in ctx.data.get("features", [])

    def prompt(self, ctx: WizardContext, prompts: Prompts) -> None:
        if not prompts.confirm("tts_enable", "Configure per-profile TTS voices? (default: text-only)", default=False):
            ctx.data["tts"] = {"enabled": False}
            return
        catalog = T.load_voice_catalog()
        provider = prompts.select("tts_provider", "TTS provider", T.provider_choices(catalog), default="edge")
        key_env = T.api_key_env(catalog, provider)
        api_key = prompts.password(f"tts_{provider}_key", f"{key_env} (blank to set later)") if key_env else ""

        account_specific = bool(catalog.get(provider, {}).get("account_specific"))
        voices = T.voices_for(catalog, provider)
        profiles = ctx.data.get("profiles", [])
        per_profile: dict[str, str] = {}
        if voices and not account_specific:
            # Fixed catalog (edge / openai / gemini): auto-assign by cycling through
            # the available voices in profile order, repeating once the list is
            # exhausted. No per-profile prompt — a provider's voice list is finite
            # (edge-tts ko-KR has only 3), so as the profile count grows the wizard
            # reuses voices by design rather than asking the user to resolve every
            # collision. Distinct where the list allows; duplicated past its end.
            vals = [v["value"] for v in voices]
            for i, p in enumerate(profiles):
                per_profile[p["profile_id"]] = vals[i % len(vals)]
        else:
            # Account-specific providers (elevenlabs / typecast / supertonic): voices
            # are per-account, so prompt for a voice id per profile.
            for p in profiles:
                pid, disp = p["profile_id"], p.get("persona_display_name", p["profile_id"])
                hint = ", ".join(f"{v['label']}={v['value']}" for v in voices[:3]) or "see provider docs"
                per_profile[pid] = prompts.text(
                    f"tts_voice_{pid}", f"Voice id for {disp} (e.g. {hint})",
                    default=(voices[0]["value"] if voices else ""))
        ctx.data["tts"] = {"enabled": True, "provider": provider,
                           "api_key_env": key_env, "api_key": api_key, "voices": per_profile}

    def apply(self, ctx: WizardContext) -> None:
        tts = ctx.data.get("tts", {})
        if not tts.get("enabled"):
            return
        catalog = T.load_voice_catalog()
        provider = tts["provider"]
        profs = ctx.data.get("profiles", [])
        staging = Path(ctx.data.get("staging_dir")
                       or (Path.home() / ".hermes" / "hermes-slack-ext" / "staging"))
        staging.mkdir(parents=True, exist_ok=True)

        # 1) provider API key -> each profile .env
        key_env, api_key = tts.get("api_key_env"), tts.get("api_key")
        if key_env and api_key:
            for p in profs:
                if p.get("env_path"):
                    secrets.write_env(Path(p["env_path"]), {key_env: api_key})

        # 2) best-effort install the built-in provider's SDK into the Hermes venv
        self._maybe_install_sdk(ctx, catalog, provider)

        # 3) stage a per-profile tts config block to merge into each config.yaml
        for p in profs:
            voice = tts.get("voices", {}).get(p["profile_id"], "")
            block = T.build_profile_tts_config(catalog, provider, voice)
            (staging / f"{p['profile_id']}.tts.yaml").write_text(
                yaml.safe_dump(block, allow_unicode=True, sort_keys=False), encoding="utf-8")

        if T.needs_plugin(catalog, provider):
            print(f"[tts] {provider} is not a Hermes built-in — {catalog.get(provider, {}).get('guide', '')}")
        print(f"[tts] staged per-profile tts config at: {staging} (merge each *.tts.yaml into the matching profile config.yaml)")

    def _maybe_install_sdk(self, ctx: WizardContext, catalog: dict, provider: str) -> None:
        pkg = T.pip_package(catalog, provider)
        if not pkg or not T.is_built_in(catalog, provider):
            return
        venv_py = ctx.hermes_root / ".venv" / "bin" / "python"
        if not venv_py.exists():
            print(f"[tts] ensure the provider SDK is installed in the Hermes venv: pip install {pkg}")
            return
        modname = pkg.replace("-", "_")
        try:
            if subprocess.run([str(venv_py), "-c", f"import {modname}"], capture_output=True).returncode == 0:
                return  # already importable
        except Exception:
            pass
        print(f"[tts] installing {pkg} into the Hermes venv…")
        try:
            subprocess.run([str(venv_py), "-m", "pip", "install", "--quiet", pkg], check=False, timeout=300)
        except Exception as exc:  # pragma: no cover - defensive
            print(f"[tts] auto-install failed ({exc}); run manually: {venv_py} -m pip install {pkg}")
