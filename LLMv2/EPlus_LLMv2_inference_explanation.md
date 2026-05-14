# EPlus-LLMv2 Inference Code Explanation

This document explains what each major segment of the researchers' `EPlus_LLMv2_inference.ipynb` code is actually doing.

## 1. Environment and Memory Setup
```python
# ⚠️ Please make sure you have adequate GPU memory.
# ⚠️ Please make sure your EnergyPlus version is 9.6 for successful running.
! pip install -U bitsandbytes -q # pip this repo at the first time.

from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
import torch
from peft import PeftModel, PeftConfig
import os

os.environ["CUDA_VISIBLE_DEVICES"] = "0"
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
```
**What it does:** 
It installs the `bitsandbytes` library required to run large models efficiently via 8-bit quantization. It imports the Hugging Face `transformers` and `peft` (Parameter-Efficient Fine-Tuning) libraries. The `CUDA_VISIBLE_DEVICES = "0"` forces PyTorch to only use the *first* GPU in the system, and `.to(device)` prepares a variable indicating that PyTorch should send tensors to that specific GPU.

## 2. Base Model Loading (FLAN-T5-XXL)
```python
# Load the EPlus-LLMv2 config.
peft_model_id = "EPlus-LLM/EPlus-LLMv2"
config = PeftConfig.from_pretrained(peft_model_id)

# Load the base LLM, flan-t5-xxl, and tokenizer
from transformers import BitsAndBytesConfig
quant_config = BitsAndBytesConfig(load_in_8bit=True)

model = AutoModelForSeq2SeqLM.from_pretrained(
    "google/flan-t5-xxl",
    quantization_config=quant_config,
    device_map="auto",
)
tokenizer = AutoTokenizer.from_pretrained("google/flan-t5-xxl")
```
**What it does:** 
The fine-tuned model (`EPlus-LLMv2`) is actually just a small set of "LoRA weights" (adapter layers), not a full model. Before applying these adapters, the script must download and load the massive 11B parameter base model: `google/flan-t5-xxl`. It uses `load_in_8bit=True` to shrink the model so it can actually fit in consumer GPU memory. It also loads the tokenizer, which translates human words into numerical IDs the AI can understand.

## 3. Applying the Fine-Tuned Weights
```python
# Load the Lora model
model = PeftModel.from_pretrained(model, peft_model_id)
```
**What it does:** 
This is the "magic" step. It takes the base `flan-t5-xxl` (which knows general English) and attaches the `EPlus-LLMv2` adapter layers (which were trained specifically to translate descriptions into EnergyPlus HVAC strings).

## 4. Configuring Generation Rules
```python
generation_config = model.generation_config
generation_config.max_new_tokens = 5000
generation_config.temperature = 0.1
generation_config.top_p = 0.1
generation_config.num_return_sequences = 1
...
```
**What it does:** 
This configures *how* the AI generates text:
*   `max_new_tokens`: Caps the output length (which takes a lot of VRAM cache).
*   `temperature = 0.1` and `top_p = 0.1`: This forces the model to be highly deterministic and "robotic." Since IDF files require strict syntax, you want the model to be extremely rigid rather than "creative" like ChatGPT.

## 5. Tokenization and Inference
```python
input_ids = tokenizer(input, return_tensors="pt", truncation=False).to(device)
generated_ids = model.generate(input_ids = input_ids.input_ids,
                           attention_mask = input_ids.attention_mask,
                           generation_config = generation_config)
generated_output = tokenizer.decode(generated_ids[0], skip_special_tokens=True)
```
**What it does:** 
It takes the long string description of the building (`input`), turns it into tokens, and sends it to the GPU. The `model.generate` function executes the inference (which takes a while depending on GPU speed). Finally, it decodes the AI's numerical output back into a human-readable text string (`generated_output`), which is raw IDF code for HVAC equipment.

## 6. Splicing the IDF String
```python
# Default thermal zones setting
zone_1 = """ZoneHVAC:EquipmentConnections,Thermal Zone 1,..."""
...
generated_output = generated_output.replace(";",";\n")
generated_output = generated_output.replace("Ideal Load System Setting for Thermal Zone 1;", zone_1)
...
file_path = "v2_nextpart.idf"
output_path = "v2_final.idf"
with open(file_path, 'r', encoding='utf-8') as file:
    nextpart = file.read()
final_text = nextpart + "\n\n" + generated_output
```
**What it does:** 
The AI model does **not** generate the geometry or the full building file. It *only* generates the HVAC system components. 
1. The code formats the output by adding line breaks after semicolons.
2. It hardcodes predefined Zone connection strings into the generated block.
3. It opens the static `v2_nextpart.idf` file (which contains the raw vertices/geometry of the building), and appends the AI's generated HVAC code to the bottom of it.
4. It saves the combined string as `v2_final.idf`, which is a complete, runnable EnergyPlus model!
