package config

import (
	"os"
	"path/filepath"
	"testing"
)

func TestLoadDefaults(t *testing.T) {
	t.Setenv("AGENTIC_PERF_API_TOKEN", "")
	t.Setenv("AGENTIC_PERF_URL", "")
	t.Setenv("APTUI_CONFIG", "/nonexistent/config.toml")

	cfg := Load("", "")
	if cfg.URL != "http://localhost:8090" {
		t.Errorf("expected default URL, got %q", cfg.URL)
	}
}

func TestLoadFlagOverridesEnv(t *testing.T) {
	t.Setenv("AGENTIC_PERF_URL", "http://env:9999")
	t.Setenv("AGENTIC_PERF_API_TOKEN", "env-token")

	cfg := Load("http://flag:1234", "flag-token")
	if cfg.URL != "http://flag:1234" {
		t.Errorf("flag URL should override env, got %q", cfg.URL)
	}
	if cfg.Token != "flag-token" {
		t.Errorf("flag token should override env, got %q", cfg.Token)
	}
}

func TestLoadEnvOverridesFile(t *testing.T) {
	t.Setenv("AGENTIC_PERF_URL", "http://env:9999")
	t.Setenv("AGENTIC_PERF_API_TOKEN", "env-token")
	t.Setenv("APTUI_CONFIG", "/nonexistent/config.toml")

	cfg := Load("", "")
	if cfg.URL != "http://env:9999" {
		t.Errorf("env URL should win, got %q", cfg.URL)
	}
	if cfg.Token != "env-token" {
		t.Errorf("env token should win, got %q", cfg.Token)
	}
}

func TestLoadFromTOML(t *testing.T) {
	dir := t.TempDir()
	tomlPath := filepath.Join(dir, "client.toml")
	os.WriteFile(tomlPath, []byte(`url = "http://toml:5555"`+"\n"+`token = "toml-tok"`+"\n"), 0600)

	t.Setenv("APTUI_CONFIG", tomlPath)
	t.Setenv("AGENTIC_PERF_URL", "")
	t.Setenv("AGENTIC_PERF_API_TOKEN", "")

	cfg := Load("", "")
	if cfg.URL != "http://toml:5555" {
		t.Errorf("expected TOML URL, got %q", cfg.URL)
	}
	if cfg.Token != "toml-tok" {
		t.Errorf("expected TOML token, got %q", cfg.Token)
	}
}

func TestLoadSecretsFile(t *testing.T) {
	dir := t.TempDir()
	secretsDir := filepath.Join(dir, "secrets")
	os.MkdirAll(secretsDir, 0700)
	os.WriteFile(filepath.Join(secretsDir, "api-token"), []byte("secret-tok\n"), 0600)

	t.Setenv("AGENTIC_PERF_HOME", dir)
	t.Setenv("AGENTIC_PERF_API_TOKEN", "")
	t.Setenv("APTUI_CONFIG", "/nonexistent/config.toml")

	cfg := Load("", "")
	if cfg.Token != "secret-tok" {
		t.Errorf("expected secrets file token, got %q", cfg.Token)
	}
}
