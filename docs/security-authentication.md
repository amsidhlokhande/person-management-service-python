# API authentication

This service protects person-management requests with **mutual TLS (mTLS) client
certificates** at the Nginx gateway. It no longer issues or accepts JWT access
or refresh tokens, and it has no username/password token endpoint.

The client presents a `.p12` file during the HTTPS handshake. Nginx verifies
the certificate against the configured client CA before forwarding a request
to FastAPI. The people router checks the gateway's certificate-verification
headers as defense in depth. Docker Compose does not publish the FastAPI port:
the gateway is the only service on the private application network that can
reach it. **Do not expose or run the FastAPI service directly as a public API**,
because the forwarded identity headers are trustworthy only behind the
configured, network-isolated gateway.

For the full explanation, local demo certificate generation, Compose setup,
client examples, and production cautions, see the
[client-certificate (mTLS) guide](client-certificate-mtls.md).

## How a request is authenticated

1. The client validates the gateway's server certificate and connects over
   HTTPS.
2. The gateway requires a client certificate and verifies its chain and
   validity against its configured client CA.
3. Only after the certificate is accepted does the gateway forward the API
   request. It overwrites `X-Client-Verify` and `X-Client-Subject` with the
   values from the TLS handshake.
4. The FastAPI people router requires a successful verification marker and a
   certificate subject. Authorization policy based on individual client
   identities must be added explicitly if clients need different permissions.

The `.p12` private key never leaves the client. The gateway does not need the
client's `.p12`; it needs the CA certificate that issued it. The gateway also
has its own server certificate and private key so clients can authenticate the
server.

## Security boundaries

- Protect each `.p12` and its password as a credential; issue separate
  certificates for each client/environment and revoke compromised certificates.
- The self-created certificates in the learning guide are **local demo
  material only**. Production must use the organization's approved CA and
  gateway configuration.
- FastAPI trusts the verification headers only because the gateway overwrites
  them and the backend port is not published. Never trust those headers if
  clients can connect to the application directly.
- A trusted certificate authenticates a client identity; it does not
  automatically define what actions that identity may perform. Configure and
  review authorization rules appropriate to the service.
- `/health`, Swagger, and ReDoc are also behind the mTLS gateway in the Compose
  deployment. Health checks and browser documentation therefore require a
  valid client certificate too.
