# Learning Materials

This directory contains shared datasets, notebooks, and other resources for all users of the JupyterHub environment.

## Usage
- Place any files or folders here that should be available to all users in their JupyterLab environment.
- The default configuration of Juno uses the `chats` directory in the work directory of the user, but this can be changed in the `docker-compose.yml` file, by setting the `CHAT_DIR` environment variable.
- The entire contents of this directory will be copied into the work directory of the user.
- Do **not** place user-specific or sensitive data here.

## Version Control
- This directory is tracked in git. Please do not remove the `.gitkeep` file. 
- The contents of this directory will not be tracked in Version Control, they are only available in this local repository and the user's work directory.

---

## 🎓 JELAI Pedagogical Personalities Demo

**Available in this directory:**

- **`JELAI_Personality_Exercises.ipynb`** - Interactive exercises with intentional errors for testing different teaching personalities
- **`sample_sales_data.csv`** - Sample dataset for the exercises
- **`pedagogical_personalities_demo.json`** - Reference copy of the personality configurations

### 🚀 Quick Start:

1. Open `JELAI_Personality_Exercises.ipynb` 
2. Run the setup cells to create your dataset
3. Work through exercises with intentional errors
4. Use `/personality [name]` commands to switch teaching styles:
   - `/personality socratic` - Learn through guided questioning
   - `/personality feynman` - Learn by teaching and explaining  
   - `/personality wing` - Learn through systematic problem decomposition
   - `/personality default` - Standard helpful assistance

### 🎯 Demo Goal:
Experience how AI tutoring can be personalized to different learning styles. Try the same error with different personalities to see how each approaches teaching!