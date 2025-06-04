# LLM Evaluation Framework

## Glossary

- **`ground_truth`**  
  The correct or ideal answer to the question (golden path) used as a reference during evaluation.

- **`context`**  
  The source content (e.g., from a PDF document) from which the answer was extracted.

- **`latency`**  
  The time taken (in seconds) to generate the response for a given query or question.

- **`coherence`**  
  Measures the logical flow and consistency of the model’s response. A coherent response stays on-topic, aligns well with the context, and maintains clarity.

- **`relevance`**  
  Evaluates how well the model’s response addresses the query or prompt and fulfills the user's information need.

- **`fluency`**  
  Refers to the grammatical correctness, readability, and natural tone of the model’s response. A fluent output resembles human-written language.

- **`similarity`**  
  Measures how closely the model's response matches the ground truth or expected answer in terms of meaning and structure.

---

## Setup Instructions

1. **Install dependencies**  
   Run the following command to install all required libraries:
   ```bash
   pip install -r requirements.txt
   ```

2. **Environment Configuration**  
    Add the required variables in a .env file. Refer to .env.sample file for the structure and list of required keys.

3. **Access Requirements**  
    If running the evaluation locally, ensure that the user has the **Cognitive Services OpenAI User** role assigned. This is necessary to authenticate and interact with Azure OpenAI resources.


## Script Overview

1. **dataset_generation.py**  
    This script is used for generating dataset for the evaluation.
    DONT RUN THIS FILE IF U ARE NOT MAKING ANY CHANGES IN questions.json  
      
    **Input:**  
    input_questions.json (List of questions/queries for the accelerator)  
    **Output:**  
    dataset.json (Includes the query, response, context, and evaluation metadata.)  

2. **api_evaluation.py**  
    This script is used to generate the evaluation matrix for the dataset provided.  
    It performs automated evaluation using Azure AI metrics such as relevance, coherence, fluency, groundedness, and similarity.   
      
    **Input:**  
    dataset.json (The output file from previous script)  
    **Output:**  
    evaluation_results.xlsx (Contains the evaluation result matrix for all the parameters) 

**Note:** All input and output files used in this project are organized within the `data/` folder: