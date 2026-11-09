# Auth testing playbook

1. MongoDB: `db.employees.findOne({role:"admin"},{password_hash:1})` -> hash starts with `$2b$`. Indexes: employees.email, login_attempts.identifier, password_tokens.token_hash, password_tokens.expires_at (TTL).
2. API:
```
curl -c cookies.txt -X POST $API/api/auth/login -H "Content-Type: application/json" -d '{"email":"wp.admin+clerk_test@example.com","password":"WorkPulse-Test-2026!"}'
curl -b cookies.txt $API/api/me
```
Login returns {"ok":true} and sets access_token + refresh_token cookies; /api/me returns the employee.
3. Invite flow: admin POST /api/auth/password-link/{id} -> path /set-password?token=...; open it, set password, user is signed in; link cannot be reused.
