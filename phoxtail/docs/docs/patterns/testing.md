# Testing

This page explains how automated testing is set up in this project, the reasoning behind the architectural choices, and how to run, write, and extend the test suite.

---

## Philosophy

All business logic in this project lives in **service layer classes**, not in views, forms, or models. A `SubscriptionService`, for example, owns every decision about credit deduction, renewal eligibility, and access control. Views, admin interfaces, and future API endpoints are intentionally thin — they delegate to a service and render the result.

This makes the service layer the natural and correct place to anchor tests:

- **No duplication.** The same rules are enforced regardless of the surface that triggers them (HTMX view, admin panel, API). Testing the service tests all of those paths at once.
- **No noise.** Tests don't need to simulate HTTP requests, parse HTML, or know about templates to verify a business rule.
- **Precision.** Each operation class (`Create`, `Renew`, etc.) exposes `authorize`, `validate`, and `perform` as distinct methods. They can be tested independently, making it easy to assert exactly which step caught an error and why.
- **Stability.** View and template code changes frequently as the UI evolves. Service layer tests are decoupled from all of that and rarely need to change when a template is updated.

Views, admin interfaces, and future API endpoints each get their own separate and thinner layer of tests that sits on top of the service tests. See [View Tests](#view-tests) for how those are written.

---

## Toolchain

| Package | Role |
|---|---|
| `pytest` | Test runner. Cleaner syntax and better output than Django's built-in unittest runner. |
| `pytest-django` | Django integration for pytest: database access, settings, the request factory, fixtures for the test client. |
| `factory-boy` | Model factories. Generates realistic model instances with minimal boilerplate. Far more maintainable than raw `setUp()` data or JSON fixtures. |
| `Faker` | Realistic dummy data (names, emails, addresses). Used by factory_boy under the hood and already in `requirements.in`. |
| `freezegun` | Freeze or travel `datetime.now()` / `timezone.now()` in tests. Essential for anything date- or time-dependent (subscription expiry, renewal start dates, etc.). |
| `pytest-cov` | Line and branch coverage reports via `coverage.py`. |

---

## Running Tests

All test commands run inside the Docker `web` container, which has access to the database and all installed packages.

```bash
# Run the full test suite
phoxtail test

# Run with additional pytest arguments
phoxtail test -- -x                          # stop on first failure
phoxtail test -- -k test_is_expired          # run tests matching a name pattern
phoxtail test -- booking/subscriptions/tests # run a specific directory
phoxtail test -- -m 'not integration'        # exclude integration-marked tests

# Run with coverage report
phoxtail test --coverage
```

---

## Test Settings

Tests run under `src/settings/test.py`, pointed to by `DJANGO_SETTINGS_MODULE = "src.settings.test"` in `pyproject.toml`.

This file does two things before importing base settings:

```python
# src/settings/test.py
import os

os.environ["FEATURE_ACTIVATE_BOOKING"] = "True"  # (1)

from .base import *  # noqa

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]  # (2)
STORAGES = { ... "staticfiles": StaticFilesStorage ... }              # (3)
```

1. **Feature flag override.** `FEATURE_ACTIVATE_BOOKING` defaults to `False` in `.env`. Setting it in `os.environ` *before* `base.py` is imported means `environ.Env.read_env()` (which uses `setdefault` semantics) never overwrites it. The booking apps are then added to `INSTALLED_APPS` by the conditional block in `base.py`.
2. **Fast password hashing.** `MD5PasswordHasher` skips the expensive PBKDF2 key stretching. Tests that create users run orders of magnitude faster.
3. **No collectstatic requirement.** `ManifestStaticFilesStorage` (used in production/development) requires a pre-built manifest file. `StaticFilesStorage` skips that, so tests never fail because `collectstatic` hasn't been run.

When adding a new feature-flagged application that should be covered by tests, add the same pattern to `test.py`.

---

## Project Structure

Tests live inside each application under a `tests/` package. This keeps them co-located with the code they cover and avoids a monolithic top-level `tests/` directory that becomes hard to navigate.

```
booking/subscriptions/
└── tests/
    ├── __init__.py
    ├── conftest.py          ← shared fixtures for this app
    ├── factories.py         ← factory_boy factories for this app's models
    └── services/
        ├── __init__.py
        ├── test_subscription_service.py   ← core service business logic
        ├── admin/
        │   ├── __init__.py
        │   ├── test_create.py
        │   └── test_renew.py
        └── public/
            ├── __init__.py
            ├── test_create.py
            └── test_renew.py
```

The `services/` sub-package mirrors the layout of the service layer itself, so it is always obvious where to find the test for any given operation.

---

## Factories

Factories are defined in `tests/factories.py` for each app. They use `factory.django.DjangoModelFactory` and `factory.Sequence` to guarantee uniqueness across tests.

```python
class SubscriptionTypeFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = SubscriptionType

    name = factory.Sequence(lambda n: f"Subscription Type {n}")
    is_active = True
    is_public = True
    duration = 30
    credits = 10
```

**Use factories when you need precise control over model state** — for example, a subscription with exactly 3 credits remaining and a specific `end_date`. Use fixtures (from `conftest.py`) when you just need a valid object and don't care about its exact field values.

```python
# conftest.py fixture — use when you just need "a subscription"
@pytest.fixture
def subscription(user, subscription_type):
    return SubscriptionFactory(user=user, subscription_type=subscription_type)

# Inline factory call — use when the test depends on specific state
def test_something():
    sub = SubscriptionFactory(credits=0, end_date=datetime.date(2020, 1, 1))
```

### Shared factories

`UserFactory`, `LocationFactory`, and `ServiceFactory` currently live in `booking/subscriptions/tests/factories.py`. As other booking apps add test suites, these should be extracted to a shared `booking/tests/factories.py` and imported from there.

---

## Writing Tests

### Database access

Mark any test that touches the database with `pytest.mark.django_db`. The most ergonomic way is to apply it at the module level:

```python
pytestmark = pytest.mark.django_db
```

pytest-django wraps each test in a transaction that is rolled back at the end, so tests are isolated from each other without any manual cleanup.

### Grouping

Use classes to group tests for the same method or operation. This keeps related assertions together and makes the test output easier to scan:

```python
class TestIsExpired:
    def test_no_end_date_returns_false(self): ...
    def test_past_end_date_returns_true(self): ...
    def test_same_day_end_date_not_yet_expired(self): ...
```

### Freezing time

Use `freezegun.freeze_time` as a decorator for any test that depends on the current date:

```python
from freezegun import freeze_time

@freeze_time("2024-06-15")
def test_past_end_date_returns_true(self):
    sub = SubscriptionFactory(end_date=datetime.date(2024, 6, 14))
    assert SubscriptionService(sub).is_expired() is True
```

### Asserting validation errors

Service operations raise `django.core.exceptions.ValidationError` on business rule violations. Test each rule in its own function:

```python
from django.core.exceptions import ValidationError

def test_raises_for_inactive_subscription_type(self, user):
    st = SubscriptionTypeFactory(is_active=False)
    with pytest.raises(ValidationError):
        SubscriptionService().admin.create(user, st)
```

Do not assert on the specific error message — that is an implementation detail that changes frequently. Only assert that the right exception type is raised.

### Custom marks

The `integration` mark is registered in the root `conftest.py`. Use it for tests that require real external services (e.g. a live payment gateway, an SMTP server):

```python
@pytest.mark.integration
def test_real_payment_webhook(): ...
```

Run everything except integration tests locally:

```bash
phoxtail test -- -m 'not integration'
```

---

## View Tests

Views in this project are thin by design — they resolve a request, call a service, and render the result. That means view tests have a narrow, well-defined responsibility: verify that the **HTTP surface** works correctly. They are not the place to re-verify business rules.

### What view tests should cover

- The URL resolves to the correct view and returns the expected status code.
- Authentication and permission are enforced — unauthenticated requests are redirected, unauthorized ones are rejected.
- A valid form submission reaches the service and triggers the expected redirect or response.
- An invalid form submission (missing required field, wrong type) returns a form-error response without calling the service.
- The correct template is rendered and the correct context keys are present.

### What view tests must not cover

- Whether a `ValidationError` fires for a specific business rule — that belongs in the service test.
- Whether credits were correctly decremented — that belongs in the service test.
- Any assertion that digs into database state to verify a domain outcome — that belongs in the service test.

If you find yourself writing `assert Subscription.objects.filter(...).exists()` inside a view test, stop and move that assertion to a service test. The view test should only care that the right response came back.

### Approach A — mock the service (recommended for most view tests)

Mocking the service keeps view tests fast and isolated. The test does not need the database and does not risk accidentally re-testing business logic.

```python
from unittest.mock import MagicMock, patch

pytestmark = pytest.mark.django_db

def test_admin_create_view_calls_service_and_redirects(client, admin_user, user, subscription_type):
    client.force_login(admin_user)

    mock_sub = MagicMock()

    with patch(
        "booking.subscriptions.views.admin.views.SubscriptionService"
    ) as MockService:
        MockService.return_value.admin.create.return_value = mock_sub
        response = client.post(url, data={"user": user.pk, "subscription_type": subscription_type.pk})

    MockService.return_value.admin.create.assert_called_once_with(user, subscription_type)
    assert response.status_code == 302
```

This test answers: "did the view hand off to the service with the right arguments and then redirect?" It does not care what the service actually does with those arguments — that is already covered by service layer tests.

### Approach B — full stack (use sparingly)

Sometimes the end-to-end flow is complex enough that running through the real service is worth it — for example, when testing an HTMX partial that updates in-place based on actual model state after the operation. In that case, skip the mock and let the real service run:

```python
pytestmark = pytest.mark.django_db

def test_subscribe_form_creates_subscription_and_renders_confirmation(
    client, user, subscription_type
):
    client.force_login(user)
    response = client.post(url, data={"subscription_type": subscription_type.pk})
    assert response.status_code == 200
    assert "subscription" in response.context
```

Even here, avoid asserting on internal domain state (credit balances, status values). Check that the response is correct and trust the service tests for everything else.

### The rule of thumb

> A view test fails when the *routing, authentication, or HTTP contract* breaks.
> A service test fails when a *business rule* breaks.

If a test could fail for either reason, it is doing too much. Split it.

---

## Adding Tests to a New Application

When a new Django app acquires service layer logic that needs coverage:

1. **Create the test package:**
   ```
   my_app/tests/__init__.py
   my_app/tests/conftest.py
   my_app/tests/factories.py
   my_app/tests/services/__init__.py
   ```

2. **Write factories** for the app's models in `factories.py`. Import any shared factories (User, Location, Service) from wherever they have been consolidated by then.

3. **Add fixtures** to `conftest.py` for the objects that most tests in this app will need.

4. **Write test files** under `tests/services/`, mirroring the layout of the service layer. One file per operation class is a good default.

5. **If the app is feature-flagged**, add `os.environ["FEATURE_ACTIVATE_X"] = "True"` to `src/settings/test.py` so its apps are included in `INSTALLED_APPS` during the test run.

No changes to `pyproject.toml` are needed — pytest discovers tests recursively from the project root.
