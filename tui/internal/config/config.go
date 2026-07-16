// Package config handles TUI configuration from TOML files,
// environment variables, and command-line flags.
package config

import (
	"os"
	"path/filepath"
	"strings"

	"github.com/BurntSushi/toml"
)

type Config struct {
	URL   string `toml:"url"`
	Token string `toml:"token"`
}

type fileConfig struct {
	URL   string `toml:"url"`
	Token string `toml:"token"`
}

// Load resolves configuration in precedence order:
// flag → env → TOML file → secrets file.
func Load(flagURL, flagToken string) Config {
	var fc fileConfig
	if path := configFilePath(); path != "" {
		toml.DecodeFile(path, &fc)
	}

	cfg := Config{
		URL:   firstNonEmpty(flagURL, os.Getenv("AGENTIC_PERF_URL"), fc.URL, "http://localhost:8090"),
		Token: firstNonEmpty(flagToken, os.Getenv("AGENTIC_PERF_API_TOKEN"), fc.Token, readSecretsFile()),
	}
	return cfg
}

func configFilePath() string {
	if v := os.Getenv("APTUI_CONFIG"); v != "" {
		return v
	}
	home, err := os.UserHomeDir()
	if err != nil {
		return ""
	}
	return filepath.Join(home, ".config", "aptui", "client.toml")
}

func readSecretsFile() string {
	home, err := os.UserHomeDir()
	if err != nil {
		return ""
	}
	apHome := os.Getenv("AGENTIC_PERF_HOME")
	if apHome == "" {
		apHome = filepath.Join(home, ".agentic-perf")
	}
	data, err := os.ReadFile(filepath.Join(apHome, "secrets", "api-token"))
	if err != nil {
		return ""
	}
	return strings.TrimSpace(string(data))
}

func firstNonEmpty(vals ...string) string {
	for _, v := range vals {
		if v != "" {
			return v
		}
	}
	return ""
}
