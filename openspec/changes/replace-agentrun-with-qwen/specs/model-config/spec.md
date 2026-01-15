# Model Configuration Specification

## ADDED Requirements

### Requirement: Qwen API Model Configuration
The system SHALL support direct configuration of Qwen (通义千问) API models without requiring AgentRun platform integration.

#### Scenario: Configure Qwen model via environment variables
- **WHEN** `QWEN_API_KEY` environment variable is set
- **THEN** the system SHALL use Qwen API for all Agent model calls
- **AND** the system SHALL read `QWEN_MODEL` environment variable for model name (with a sensible default if not provided)

#### Scenario: Backward compatibility with AgentRun
- **WHEN** `QWEN_API_KEY` is not set but `AGENTRUN_MODEL_NAME` is set
- **THEN** the system SHALL fall back to AgentRun model configuration
- **AND** the system SHALL maintain existing behavior

#### Scenario: Error handling for missing configuration
- **WHEN** neither `QWEN_API_KEY` nor `AGENTRUN_MODEL_NAME` is set
- **THEN** the system SHALL raise a clear error message indicating required configuration

## MODIFIED Requirements

### Requirement: Model Provider Selection
The system SHALL prioritize Qwen API configuration over AgentRun configuration when both are available.

#### Scenario: Qwen takes precedence
- **WHEN** both `QWEN_API_KEY` and `AGENTRUN_MODEL_NAME` are set
- **THEN** the system SHALL use Qwen API configuration
- **AND** the system SHALL ignore AgentRun configuration


