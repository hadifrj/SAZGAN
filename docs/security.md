# Security

Security-sensitive behavior is implemented in the application and should be preserved when making changes.

## Application controls

- Authentication and session handling are centralized in the existing security/auth modules.
- Route access is enforced through the application's access-control helpers.
- CSRF protection and login protection are part of the existing security layer.
- File access and upload handling should remain constrained to the intended application directories.
- Request-size limits should remain enabled for production deployments.
- Production deployments should use the configured WSGI server rather than Flask's development server.

## Android WebView

The Android client restricts file/content access and rejects invalid TLS certificates. WebView cleanup also clears transient session state when the client is destroyed.

## Secrets

Never commit secret keys, private keys, credentials or live environment configuration. Supply production secrets through the deployment environment.

Useful environment variables include the configured secret key and secure-session settings. Do not place their actual values in source control.

## Production checklist

- Use HTTPS with a valid certificate.
- Set a strong random application secret.
- Use secure cookies when HTTPS is enabled.
- Keep dependencies updated.
- Restrict database and upload directories from direct public access.
- Run health and smoke checks after deployment.
- Keep backups outside the release archive.

## Reporting and maintenance

Security changes should be documented by behavior and control, not by temporary audit names or internal development stages. Detailed historical investigation notes do not belong in the source package.
