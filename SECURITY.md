# Security Policy

- Never commit Kaggle API tokens, Strata API keys, OpenCode credential files, model weights, runtime cache archives, or notebook output containing secrets.
- Use Kaggle's Secrets manager for `KAGGLE_API_TOKEN`. Enable the secret only for the notebook that requires it.
- Keep model and runtime Kaggle datasets private. The notebook does not pass `--public` to the Kaggle CLI.
- The Strata public endpoint must reject requests without a bearer key (HTTP 401/403) before OpenCode use.
- Cloudflare Quick Tunnel URLs are public and temporary. Keep the API key private and stop the tunnel when finished.
- Verify every model's license and upstream terms before uploading model files, even to a private dataset.
- Report security issues privately to the repository maintainer rather than opening a public issue with secrets or personally identifying information.
