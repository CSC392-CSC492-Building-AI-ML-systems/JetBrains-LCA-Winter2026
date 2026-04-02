# 🏟️ Long Code Arena Baselines
## Bug localization

This directory contains the code for the Bug localization benchmark. The challenge is: 
given an issue with the bug description and the repository code in the state where the issue is reproducible, identify the files within the project that need to be modified to address the reported bug.

We provide scripts for [data collection and processing](./src/data), [data exploratory analysis](./src/notebooks), as well as several [baselines implementations](./src/baselines) for solving the task with [the calculation of evaluation metrics](./src/notebooks).

## 💾 Install dependencies
We provide dependencies for the pip dependency manager, so please run the following command to install all the required packages:
```shell
pip install -r requirements.txt
```

## 🤗 Dataset

All the data is stored in [HuggingFace 🤗](JetBrains-Research/lca-bug-localization). It contains:

* A **dataset** with the bug localization data (issue description, SHA of the repo in initial state, and SHA of the repo after fixing the issue).
You can access the data using the [datasets](https://huggingface.co/docs/datasets/en/index) library:
    ```python3
    from datasets import load_dataset
    
    # Select a configuration from ["py", "java", "kt", "mixed"]
    configuration = "py"
    # Select a split from ["dev", "train", "test"]
    split = "dev"
    # Load data
    dataset = load_dataset("JetBrains-Research/lca-bug-localization", configuration, split=split)
    ```
    ...where the labels are:\
    `dev` — all the collected data;\
    `test` — manually selected data ([labeling artifacts](https://docs.google.com/spreadsheets/d/1cEyFHjse-iUYQlUO7GO5KpqkvJ3wu6vheou4W61TMOg/edit?usp=sharing));\
    `train` — all the collected data that is not in `test`;

    ...and configurations are:\
    `py` — only `.py` files in diff;\
    `java` — only `.java` files in diff;\
    `kt` — only `.kt` files in diff;\
    `mixed` — at least one `.py`, `.java`, or `.kt` file and maybe files with another extensions in diff.


* **Archived repos** (from which we can extract repository content at different stages and get diffs that contains bugs fixes).\

## ⚙️ Baselines

* Embedding-based:
  * [TF-IDF](https://scikit-learn.org/stable/modules/generated/sklearn.feature_extraction.text.TfidfVectorizer.html#sklearn.feature_extraction.text.TfidfVectorizer);
  * [GTE](https://huggingface.co/thenlper/gte-large);
  * [CodeT5](https://huggingface.co/Salesforce/codet5p-110m-embedding);
  * [BM25]().
  
* Chat-based (LLMs):
  * [GPT-3.5 & GPT-4](https://platform.openai.com/docs/models) (OpenAI);
  * [Gemini 2.5 Flash](https://deepmind.google/technologies/gemini/flash/) (Google);
  * [Claude 4.5 Haiku](https://www.anthropic.com/claude) (Anthropic).

## 🚀 Running the Baselines & Evaluation

You can execute the chat-based models using the `run.py` script via Hydra, and calculate their accuracy using `eval.py`. Ensure your respective API keys are set as environment variables (`OPENAI_API_KEY`, `GOOGLE_API_KEY`, or `ANTHROPIC_API_KEY`) before running.

**1. Run OpenAI (GPT-3.5)**
```shell
python3 -m src.baselines.run backbone=gpt-3.5 data_source.split=dev 
python3 -m src.baselines.eval data_source.split=dev run_id=openai-gpt-3.5-turbo-1106_issue_only 
```

**2. Run Gemini**
```shell
python3 -m src.baselines.run backbone=gemini-2.5-flash data_source.split=dev 
python3 -m src.baselines.eval data_source.split=dev run_id=gemini-2.5-flash_issue_only 
```

**3. Run Claude**
```shell
python3 -m src.baselines.run backbone=claude-4.5-haiku data_source.split=dev 
python3 -m src.baselines.eval data_source.split=dev run_id=claude-haiku-4-5_issue_only
```

## 📊 Evaluation Metrics

The pipeline includes automated metric collection during generation and evaluation to assess both efficiency and retrieval quality.

* **Performance Metrics (Generation):** Tracks execution efficiency via `run.py`.
  * Total / Average Time per instance
  * Token Usage & Estimated Cost (USD)
  * Valid JSON output compliance rate
  * Average Files Guessed & Empty Predictions
* **Accuracy Metrics (Evaluation):** Measures retrieval success via `eval.py`.
  * **Precision, Recall, & F1 Score**
  * **False Positive Rate (FPR)**
  * **Success Rates:** Identifies the percentage of instances where the model guessed *All Correct*, *At Least One Correct*, or *All Incorrect* files.