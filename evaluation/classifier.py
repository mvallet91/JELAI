import dspy
import os
import json
from dotenv import load_dotenv
OLLAMA_API_BASE = os.getenv("ollama_url", "http://localhost:11434") # Your Ollama URL
lm = dspy.LM('ollama_chat/gemma3:4b', api_base=OLLAMA_API_BASE, api_key='')
dspy.configure(lm=lm)

# from typing import Literal

# class HelpType(dspy.Signature):
#     """Classify the type of request based on help-seeking theory."""

#     sentence: str = dspy.InputField()
#     category: Literal['instrumental', 'executive', 'other'] = dspy.OutputField()

# sentence = "how do i import a csv into pandas?"  

# classify = dspy.Predict(HelpType)
# help_type = classify(sentence=sentence)
# print(help_type.category)  

from typing import Literal

class Classify(dspy.Signature):
    """Classify sentiment of a given sentence."""

    sentence: str = dspy.InputField()
    sentiment: Literal['positive', 'negative', 'neutral'] = dspy.OutputField()
    confidence: float = dspy.OutputField()

classify = dspy.Predict(Classify)
classify(sentence="This book was super fun to read, though not the last chapter.")