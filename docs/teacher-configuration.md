# Teacher configuration

Teachers control how the tutor works. All settings are in the directory
`jupyterhub-docker/middleware/inputs/`. You can edit the files there, or on
the **teacher settings page**:

```
http://<server>:8004/teacher-settings      (user name: teacher, password: TEACHER_PASSWORD)
```

The settings page checks a file before it saves it. The tutor uses the new
settings for the next student message. A restart is not necessary.

## The tutor pipeline

For each student message, the tutor does these steps:

1. **Identification**: it finds what the student does. It reads the recent
   notebook activity, finds the concepts in the executed code, matches the
   question to a learning objective, and updates the learner model
   (knowledge, metacognition, affect).
2. **Classification**: it asks the LLM to put the message in one category
   (by default `instrumental`, `executive` or `other`).
3. **Intervention**: it selects the first reactive rule that matches the
   category and the history of the student, and adds the hint of the rule to
   the tutor prompt. Separately, the tutor can send a proactive message when
   the student has a problem and does not ask for help.

The file `agent_config.yaml` controls all three steps.

## agent_config.yaml

| Section | What it controls |
|---|---|
| `agent` | The name of the tutor in the chat. |
| `llm.models` | Optional model for each task. Empty values use the `.env` file. |
| `prompts` | The files with the system prompts of the tutor and the expert agent. |
| `expert_agent.enabled` | Set to `false` to use one LLM request less per question. |
| `identification.concept_patterns` | Code substrings that show that the student used a concept. |
| `identification.knowledge_components` | Which concepts increase which knowledge score of the learner model. |
| `identification.learner_states` | The thresholds for "Trial and Error", "Help Avoidant", "Reflective", "Frustrated" and "Flow". |
| `classification` | The categories, their descriptions and the prompt for the LLM. |
| `interventions.reactive` | The rules that add hints to the tutor prompt. |
| `interventions.needs_guidance` | When the dashboard shows that a student needs guidance. |
| `proactivity` | When and how the tutor sends messages without a question. |
| `message_gateway` | Text patterns that the tutor must never send to a student. |
| `commands` | The chat commands `/report` and the optional completion code. |

If you remove a key from the file, the tutor uses the original value. If the
file has a syntax error, the tutor uses the original file and the settings
page shows the error.

### Example: classify by phase of self-regulated learning

```yaml
classification:
  categories:
    - name: planning
      description: Goal setting, strategy selection or task analysis.
    - name: performance
      description: Task execution, self-monitoring or self-control.
    - name: self-reflection
      description: Self-evaluation of the work or of the result.
    - name: other
      description: Messages that are not about learning.
  default_category: other
  prompt: |
    Classify the message of a student by the phase of Zimmerman's model of
    self-regulated learning:
    {categories}

interventions:
  reactive:
    rules:
      - name: Plan before code
        category: performance
        previous_category: performance
        min_streak: 3
        hint: >-
          The student asks many questions about the execution. Ask the student
          to make a short plan of the next steps before they continue.
      - name: Praise reflection
        category: self-reflection
        hint: Give short, specific praise for the reflection.
```

### Reactive rule conditions

| Key | Meaning |
|---|---|
| `category` | Necessary. The category of the current message. |
| `previous_category` | The category of the previous message. |
| `streak` | The exact number of consecutive messages in this category, including the current one. |
| `min_streak` | The minimum number of consecutive messages in this category. |
| `hint` | The text that goes into the tutor prompt. |

The tutor uses the **first** rule that matches. Put the most specific rules
first.

### Placeholders

Text values can contain these placeholders:

- `{agent_name}`: the name of the tutor
- `{question}`: the current student message
- `{last_<category>_example}`: the last student message in a category, for
  example `{last_executive_example}`
- `{categories}`: only in the classification prompt, the list of categories

## Other input files

| File or directory | Content |
|---|---|
| `ta_system_prompt.txt` | The system prompt of the tutor. |
| `ea_system_prompt.txt` | The system prompt of the expert agent. |
| `assignment_descriptions/<notebook>.txt` | The description of an assignment. |
| `learning_objectives/<notebook>.txt` | The learning objectives, one on each line. |
| `next_steps/<notebook>.txt` | Next steps for the `/report` command, one on each line. |
| `ab_experiments.json` | Optional A/B experiment: groups of students with different prompts or without hints. |

The name of the file must be the same as the name of the notebook and of the
chat (for example `Task1.ipynb`, `Task1.chat` and `Task1.txt`). The file
`default.txt` applies to all notebooks that do not have a file.

If a `.txt` file does not exist, the tutor uses the `.txt.sample` file. On the
settings page, open the sample and click **Save** to make your own copy.

### A/B experiments

To compare two groups of students, set `active_experiment_id` in
`ab_experiments.json` to the ID of an experiment. Each student goes into one
group for the full experiment. A group with `"profile_hint_strategy": "none"`
gets no reactive hints. A group can use a different prompt file with
`"system_prompt_file"`. Set `active_experiment_id` to `""` to stop the
experiment.
