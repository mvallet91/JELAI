# Demo course

A small course with synthetic data for a demonstration of JELAI with one
student and one teacher.

## Content

| Path | Purpose |
|---|---|
| `materials/Task1.ipynb` | The notebook of the student. |
| `materials/data/study_hours.csv` | Synthetic data of 60 students. Three values are missing on purpose. |
| `inputs/assignment_descriptions/Task1.txt` | The description of the assignment for the tutor. |
| `inputs/learning_objectives/Task1.txt` | The learning objectives. |
| `inputs/next_steps/Task1.txt` | The options of the `/report` command. |

## Install the demo course

1. Open the teacher settings page and upload `materials/Task1.ipynb` and
   `materials/data/study_hours.csv` in **Course materials**. To keep the
   `data` folder, make a ZIP file of the content of `materials` and upload
   the ZIP file.
2. Select `Task1.ipynb` as the notebook that opens after login.
3. Copy the three files in `inputs/` to the same folders in
   `jupyterhub-docker/middleware/inputs/`, or paste their text on the settings
   page (Assignment descriptions, Learning objectives, Next steps, name `Task1`).

## Demonstration script (about 10 minutes)

**Student**

1. Sign up and log in. `Task1.ipynb` opens.
2. Run the first cell with a typing error, for example `import panas as pd`. The cell fails.
3. Open the chat panel, make the chat `chats/Task1.chat`, and ask: "Why does my import fail?"
   The tutor gives a hint and does not give the full solution.
4. Ask for a direct answer two or three times, for example "Just give me the code for step 3."
   The tutor classifies these messages as `executive`, and the reactive rule for
   repeated executive requests changes the answer.
5. Ask a question about a concept, for example "What does groupby do?" This is an `instrumental` message.
6. Type `/report` to get a summary and the next-step options.

**Teacher**

1. Open the teacher dashboard (`/teacher-view`). Select the student. The story shows
   the cell runs, the error and the chat messages.
2. Open the settings page (`/teacher-settings`). In `agent_config.yaml`, change a hint
   in `interventions.reactive.rules` and click **Save**.
3. The student asks one more question. The answer uses the new hint, without a restart.
4. Upload one more file in **Course materials**. It is in the folder of the student
   within one minute.
