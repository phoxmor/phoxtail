"""Tests for CLI template rendering."""

from phoxtail.utils.templates import render_template


class TestDockerfileTemplate:
    def test_renders_with_python_version(self):
        result = render_template(
            "docker/Dockerfile",
            {
                "python_version": "3.12",
                "port": 80,
                "gunicorn_workers": 3,
            },
        )
        assert "python:3.12-slim-bookworm" in result

    def test_renders_port(self):
        result = render_template(
            "docker/Dockerfile",
            {
                "python_version": "3.12",
                "port": 8000,
                "gunicorn_workers": 3,
            },
        )
        assert "EXPOSE 8000" in result
        assert "0.0.0.0:8000" in result

    def test_renders_gunicorn_workers(self):
        result = render_template(
            "docker/Dockerfile",
            {
                "python_version": "3.12",
                "port": 80,
                "gunicorn_workers": 5,
            },
        )
        assert "-w 5" in result

    def test_has_development_and_production_stages(self):
        result = render_template(
            "docker/Dockerfile",
            {
                "python_version": "3.12",
                "port": 80,
                "gunicorn_workers": 3,
            },
        )
        assert "AS development" in result
        assert "AS production" in result


class TestComposeTemplate:
    def _render(self, environment="development", activate_booking=False):
        return render_template(
            "docker/docker-compose.yaml",
            {
                "environment": environment,
                "image_name": "phoxmor/test:latest",
                "postgres_version": "17",
                "pg_data_path": "/var/lib/postgresql/data",
                "activate_booking": activate_booking,
            },
        )

    def test_dev_has_tailwind_service(self):
        result = self._render("development")
        assert "tailwind" in result

    def test_dev_has_docs_service(self):
        result = self._render("development")
        assert "docs" in result
        assert "mkdocs" in result

    def test_dev_does_not_have_nginx(self):
        result = self._render("development")
        assert "nginx:" not in result
        assert "certbot" not in result

    def test_dev_exposes_port_80(self):
        result = self._render("development")
        assert '"80:80"' in result

    def test_prod_has_nginx_and_certbot(self):
        result = self._render("production")
        assert "nginx:" in result
        assert "certbot" in result

    def test_prod_does_not_have_tailwind(self):
        result = self._render("production")
        assert "tailwind:" not in result

    def test_booking_off_no_redis(self):
        result = self._render("development", activate_booking=False)
        assert "redis" not in result
        assert "celery" not in result

    def test_booking_on_has_redis_and_celery(self):
        result = self._render("development", activate_booking=True)
        assert "redis:" in result
        assert "celery-worker:" in result
        assert "celery-beat:" in result
        assert "redis_data:" in result

    def test_booking_on_web_depends_on_redis(self):
        result = self._render("development", activate_booking=True)
        # Find the web service section and check redis dependency
        lines = result.split("\n")
        in_web = False
        in_depends = False
        has_redis_dep = False
        for line in lines:
            if line.strip().startswith("web:"):
                in_web = True
            elif in_web and line.strip().startswith("depends_on:"):
                in_depends = True
            elif in_web and in_depends and "redis" in line:
                has_redis_dep = True
                break
            elif (
                in_web
                and not line.startswith(" ")
                and not line.startswith("\t")
                and line.strip()
            ):
                if line.strip() != "web:" and ":" in line:
                    break
        assert has_redis_dep

    def test_image_name_rendered(self):
        result = self._render("development")
        assert "phoxmor/test:latest" in result

    def test_postgres_version_rendered(self):
        result = self._render("development")
        assert "postgres:17" in result


class TestNginxInitialTemplate:
    def test_renders_static_content(self):
        result = render_template("nginx/initial.conf", {})
        assert "listen 80" in result
        assert "acme-challenge" in result
        assert "proxy_pass http://web:80" in result


class TestNginxProductionTemplate:
    def _render(self, wildcard=False):
        domain = "example.com"
        if wildcard:
            server_name = f"{domain} .{domain}"
            redirect_target = "$host"
        else:
            server_name = f"{domain} www.{domain}"
            redirect_target = domain
        return render_template(
            "nginx/production.conf",
            {
                "domain": domain,
                "server_name": server_name,
                "redirect_target": redirect_target,
                "wildcard": wildcard,
            },
        )

    def test_standard_has_www_redirect(self):
        result = self._render(wildcard=False)
        assert "server_name www.example.com" in result
        assert "return 301 https://example.com" in result

    def test_wildcard_has_dot_domain(self):
        result = self._render(wildcard=True)
        assert "example.com .example.com" in result

    def test_ssl_certificates_reference_domain(self):
        result = self._render()
        assert "/etc/letsencrypt/live/example.com/fullchain.pem" in result
        assert "/etc/letsencrypt/live/example.com/privkey.pem" in result

    def test_has_security_headers(self):
        result = self._render()
        assert "X-Content-Type-Options" in result
        assert "X-Frame-Options" in result

    def test_has_gzip(self):
        result = self._render()
        assert "gzip on" in result

    def test_has_http2(self):
        result = self._render()
        assert "http2 on" in result


class TestEnvDevelopmentTemplate:
    def test_renders_development_env(self):
        result = render_template(
            "env/development.env",
            {
                "secret_key": "test-secret",
                "site_name": "My Site",
                "postgres_db": "mydb",
                "postgres_user": "myuser",
                "postgres_password": "mypass",
                "allow_signup": True,
                "activate_dashboard": False,
                "activate_booking": True,
            },
        )
        assert "DJANGO_ENV=development" in result
        assert "SECRET_KEY=test-secret" in result
        assert "SITE_NAME=My Site" in result
        assert "POSTGRES_DB=mydb" in result
        assert "FEATURE_ALLOW_SIGNUP=true" in result
        assert "FEATURE_ACTIVATE_DASHBOARD=false" in result
        assert "FEATURE_ACTIVATE_BOOKING=true" in result


class TestEnvProductionTemplate:
    def _render(self, use_smtp=False):
        context = {
            "secret_key": "prod-secret",
            "site_name": "Prod Site",
            "postgres_db": "proddb",
            "postgres_user": "produser",
            "postgres_password": "prodpass",
            "domain": "example.com",
            "domain_email": "admin@example.com",
            "allowed_hosts": "example.com",
            "csrf_origins": "https://example.com",
            "use_smtp": use_smtp,
            "allow_signup": False,
            "activate_dashboard": False,
            "activate_booking": False,
        }
        if use_smtp:
            context.update(
                {
                    "email_host": "smtp.gmail.com",
                    "email_port": "587",
                    "email_use_tls": True,
                    "email_host_user": "user@gmail.com",
                    "email_host_password": "app-password",
                    "default_from_email": "noreply@example.com",
                }
            )
        return render_template("env/production.env", context)

    def test_renders_production_env(self):
        result = self._render()
        assert "DJANGO_ENV=production" in result
        assert "DOMAIN=example.com" in result

    def test_smtp_enabled(self):
        result = self._render(use_smtp=True)
        assert "USE_SMTP_EMAIL_BACKEND=true" in result
        assert "EMAIL_HOST=smtp.gmail.com" in result
        assert "EMAIL_USE_TLS=true" in result

    def test_smtp_disabled(self):
        result = self._render(use_smtp=False)
        assert "USE_SMTP_EMAIL_BACKEND=false" in result
        assert "EMAIL_HOST" not in result
