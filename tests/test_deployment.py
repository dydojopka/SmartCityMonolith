"""Validate both city topologies without starting containers or opening databases."""
import json
import os
from pathlib import Path
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
PORTS = {
    "IDENTITY_PORT": "38001",
    "TRANSPORT_PORT": "38002",
    "UTILITY_PORT": "38003",
    "ENVIRONMENT_PORT": "38004",
    "BILLING_PORT": "38005",
    "NOTIFICATION_PORT": "38006",
    "FRONTEND_PORT": "35173",
}


def compose_config(filename, **overrides):
    environment = os.environ.copy()
    for key in (*PORTS, "JWT_SECRET", "SERVICE_TOKEN", "SENSOR_API_KEY",
                "CORS_ORIGINS", "DEMO_PAYMENTS_ENABLED", "NOTIFICATION_FAIL_SEND",
                "COMPOSE_PROJECT_NAME", "COMPOSE_PROFILES", "COMPOSE_ENV_FILES"):
        environment.pop(key, None)
    environment.update(overrides)
    result = subprocess.run(
        ["docker", "compose", "--env-file", "/dev/null", "-f", filename,
         "config", "--format", "json"],
        cwd=ROOT, env=environment, capture_output=True, text=True, timeout=30,
        check=True,
    )
    return json.loads(result.stdout)


class DeploymentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = compose_config("smart-city/docker-compose.yml")
        cls.hybrid = compose_config("compose.yml")

    def test_only_selected_pair_is_replaced(self):
        unchanged = {"identity-service", "transport-service", "environment-service",
                     "billing-service", "frontend"}
        self.assertEqual(set(self.original["services"]),
                         unchanged | {"utility-service", "notification-service"})
        self.assertEqual(set(self.hybrid["services"]), unchanged | {"app"})
        for name in unchanged:
            self.assertEqual(self.original["services"][name]["build"],
                             self.hybrid["services"][name]["build"])

    def test_internal_notification_address_reaches_monolith(self):
        services = self.hybrid["services"]
        self.assertIn("notification-service",
                      services["app"]["networks"]["default"]["aliases"])
        for name in ("transport-service", "billing-service"):
            self.assertEqual(services[name]["environment"]["NOTIFICATION_URL"],
                             "http://notification-service:8000")
            self.assertEqual(set(services[name]["depends_on"]), {"app"})
            self.assertEqual(services[name]["depends_on"]["app"]["condition"],
                             "service_healthy")

    def test_database_files_and_projects_are_separate(self):
        self.assertEqual(self.original["name"], "smart-city-original")
        self.assertEqual(self.hybrid["name"], "smart-city-hybrid")
        for config, expected in ((self.original, 6), (self.hybrid, 5)):
            with self.subTest(project=config["name"]):
                urls = [service["environment"]["DATABASE_URL"]
                        for name, service in config["services"].items()
                        if name != "frontend"]
                self.assertEqual(len(urls), expected)
                self.assertEqual(len(set(urls)), expected)
                self.assertTrue(all(url.startswith("sqlite:////data/") for url in urls))
                self.assertEqual(len(config["volumes"]), expected)
                for volume in config["volumes"].values():
                    self.assertFalse(volume.get("external", False))
                    self.assertTrue(volume["name"].startswith(config["name"] + "_"))

    def test_public_ports_and_auth_settings_are_preserved(self):
        for config in (self.original, self.hybrid):
            with self.subTest(project=config["name"]):
                ports = [port for service in config["services"].values()
                         for port in service.get("ports", [])]
                self.assertEqual({port["published"] for port in ports},
                                 {"8001", "8002", "8003", "8004", "8005", "8006", "5173"})
                self.assertTrue(all(port["host_ip"] == "127.0.0.1" for port in ports))
                jwt_secrets = {service["environment"]["JWT_SECRET"]
                               for service in config["services"].values()
                               if "JWT_SECRET" in service.get("environment", {})}
                tokens = {service["environment"]["SERVICE_TOKEN"]
                          for service in config["services"].values()
                          if "SERVICE_TOKEN" in service.get("environment", {})}
                self.assertEqual(jwt_secrets, {"development-jwt-secret"})
                self.assertEqual(tokens, {"development-service-token"})
                self.assertNotIn("SERVICE_TOKEN", config["services"]["frontend"]["environment"])

    def test_alternative_ports_update_browser_urls_and_cors(self):
        for filename in ("compose.yml", "smart-city/docker-compose.yml"):
            config = compose_config(filename, **PORTS)
            with self.subTest(filename=filename):
                services = config["services"]
                published = {port["published"] for service in services.values()
                             for port in service.get("ports", [])}
                self.assertEqual(published, set(PORTS.values()))
                browser = services["frontend"]["environment"]
                for service in ("IDENTITY", "TRANSPORT", "UTILITY", "ENVIRONMENT", "BILLING"):
                    self.assertEqual(browser[f"VITE_{service}_API_URL"],
                                     f"http://localhost:{PORTS[f'{service}_PORT']}")
                for service in services.values():
                    env = service.get("environment", {})
                    if "CORS_ORIGINS" in env:
                        self.assertEqual(env["CORS_ORIGINS"], "http://localhost:35173")


if __name__ == "__main__":
    unittest.main()
