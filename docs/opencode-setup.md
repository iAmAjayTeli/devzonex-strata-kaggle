# OpenCode V2 connection

1. Keep Strata and Cloudflare Tunnel running in Kaggle.
2. Copy the temporary HTTPS URL from the notebook output.
3. In the Kaggle shell, run `strata launch --show-key` and copy the key privately.
4. Save the key in a local ignored file: `~/.config/opencode/strata-key.txt`.
5. Merge the provider object printed by the notebook into the existing `providers` map in `opencode.jsonc`. Do not replace the rest of the config.
6. Restart OpenCode and select the `strata/<model-id>` model.
7. Start a fresh OpenCode session after changing provider or context settings.

Keep the key out of GitHub and chat. The Quick Tunnel URL is temporary and changes after tunnel restart.

8. The generated model configuration includes `reasoningEffort: "none"` for the configured model entry.
