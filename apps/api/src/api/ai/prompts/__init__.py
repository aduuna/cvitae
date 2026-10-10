"""System prompts and request builders, one module per task (docs/BACKEND.md, Prompt rules).

User content goes inside tags (<cv>, <job_description>, <profile>) so the model can tell data from
instructions. Change PROMPT_VERSION whenever a prompt changes; it is stored on every ai_runs row.
"""
