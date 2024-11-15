# GPT-Based Custom Remediations

In certain cases, configuration remediations may fall outside of the standard negation and idempotency workflows that `hier_config` is built to handle. Previously, addressing these edge cases required manually crafting specific remediation steps. However, with the advent of AI, particularly generative pre-trained transformers (GPT), it’s now possible to dynamically generate these custom remediations.

The example below demonstrates how to integrate a GPT client for AI-driven remediations. While this example uses OpenAI's ChatGPT, `hier_config` can work with any compatible GPT model—such as Claude or self-hosted models like Ollama GPT—so long as the client provides similar functionality.

### Code Walkthrough and Explanation

1. Import and Configuration Loading
```python
import os
from hier_config import WorkflowRemediation, get_hconfig
from hier_config.utils import load_device_config
from hier_config.models import Platform, GPTRemediationRule, MatchRule, GPTRemediationExample
from hier_config.clients import ChatGPTClient
```

Necessary modules are imported, including the `WorkflowRemediation` class for handling remediation, as well as a client interface—in this case, `ChatGPTClient` for connecting to GPT. For other GPT models, you can replace `ChatGPTClient` with your own client class.

```python
running_config = load_device_config("./tests/fixtures/running_config_acl.conf")
generated_config = load_device_config("./tests/fixtures/generated_config_acl.conf")
```
Here, the current and intended configurations are loaded from files, serving as inputs for comparison and remediation.

2. Initialize `WorkflowRemiation`:
```python
wfr = WorkflowRemediation(
        running_config=get_hconfig(Platform.CISCO_IOS, running_config),
        generated_config=get_hconfig(Platform.CISCO_IOS, generated_config)
)
```
This initializes `WorkflowRemediation` with the configurations for a Cisco IOS platform, setting up the object that will manage the remediation workflow.

3. Define a GPT-Based Remediation Rule:
```python
description = (
    "When remediating an access-list on Cisco IOS devices, follow these steps precisely:\n"
    " 1. **Resequence the access-list:**\n"
    "    * **Action**: Resequence the access-list so that each sequence number is a multiple of 10.\n"
    "    * **Condition**: If a sequence number in the running config isn't divisible by 10, resequence it to the nearest 10, starting at 10.\n"
    " 2. **Add Temporary Permit Statement:**\n"
    "    * **Action**: Insert a temporary `'permit any'` statement at sequence number `1`.\n"
    "    * **Purpose**: Ensures there's always a valid permit in place during modifications.\n"
    " 3. **Apply Required Changes:**\n"
    "    * **Action**: Update the access-list with the new permit statements as per the generated configuration.\n"
    " 4. **Remove Temporary Permit Statement:**\n"
    "    * **Action**: Remove the temporary `'permit any'` statement added at sequence number `1`.\n"
    "\n"
    " **Important**:\n"
    " **When issuing `no` commands to remove existing entries after resequencing, USE THE"
    " RESEQUENCED SEQUENCE NUMBERS, NOT THE ORIGINAL SEQUENCE NUMBERS FROM THE"
    " RUNNING CONFIGURATION.**"
)
lineage = (MatchRule(startswith="ip access-list"),)
running = "ip access-list extended TEST\n  12 permit ip host 10.0.0.1 any"
remediation = "ip access-list resequence TEST 10 10\nip access-list extended TEST\n  1 permit ip any any\n  no 10\n  10 permit ip host 10.0.0.2 any\n  no 1"
example = GPTRemediationExample(running_config=running, remediation_config=remediation)
gpt_rule = GPTRemediationRule(description=description, lineage=lineage, example=example)
```
Here:
  * `description`: Outlines specific remediation steps that GPT should apply.
  * `lineage`: Specifies MatchRule criteria to identify access-list configurations.
  * `example`: Provides a running configuration and remediation example for added context.
  * `gpt_rule`: Combines the description, lineage, and example into a GPTRemediationRule.

4. Load AI Remediation Rules:
```python
wfr.running_config.driver.gpt_remediation_rules.append(gpt_rule)
```
This appends the custom rule to `gpt_remediation_rules`, making it available for GPT to apply.

5. Set Up and Load the GPT Client:
```python
# Example using ChatGPT, but can be replaced with other clients
gpt_client = ChatGPTClient(api_key=os.getenv("OPENAI_API_KEY"), model="gpt-4o-mini")
wfr.set_gpt_client(gpt_client)
```

In this example, `ChatGPTClient` is used for integration with OpenAI's GPT, but you can replace it with any other client class—such as Claude’s API client or a self-hosted Ollama GPT model—so long as the client provides a `generate_plan` method (or equivalent) for producing responses from a given prompt.

```python
# For a different client (e.g., Claude or Ollama)
# gpt_client = YourCustomGPTClient(api_key="your_api_key", model="claude-v1")
# wfr.set_gpt_client(gpt_client)
```
6. Generate GPT-Based Remediation:
```python
remediation = wfr.gpt_remediation_config()
```
This method builds the GPT-generated remediation based on the `gpt_rule`.

### Behind the Scenes

In the background, `hier_config` constructs the prompt and context to pass to GPT:

1. Context Creation:
```python
contexts = [item for item in wfr._build_remediation_context()]
```
This function builds the context needed for remediation by iterating over `_build_remediation_context`, which selects configurations matching the specified lineage.

2. Prompt Construction:
```
prompt = wfr._build_gpt_prompt(contexts[0])
```
Using the gathered context, `wfr._build_gpt_prompt` creates a structured prompt. The prompt includes:

  * `Description`: The remediation steps (e.g., resequencing and temporary changes).
  * `Example`: A sample configuration state to guide GPT’s response.

3. GPT Generates the Plan: GPT uses this prompt to generate commands following the custom rules, such as resequencing access-lists or adding/removing temporary statements.

This setup makes it possible to leverage any GPT model for custom configuration adjustments in `hier_config`, providing flexibility across various network automation scenarios.
