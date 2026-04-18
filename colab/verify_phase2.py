import os
import sys

# Ensure backend imports work
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "backend")))

from backend.ai_generator import AIPipelines

def run_test():
    secrets_path = "secrets.json"
    template_path = "templates/Base.idf"
    
    print("Initializing AIPipelines...")
    ai = AIPipelines(secrets_path=secrets_path, template_path=template_path)
    
    prompt = "I want a perfectly square house that is exactly 12 meters long and 12 meters wide. Make the height 3.5 meters. I want the exterior walls to use 2x4 Wood Stud R11 construction, and the roof also to use wood stud construction."
    config = {"weather_file": "weather.epw"}
    
    print(f"\nUser Prompt: {prompt}")
    
    # Try gemini first, then hf if it fails
    model = "gemini"
    print(f"\nRunning Generation with {model}...")
    final_idf = ai.generate_idf_from_text(prompt, config, model_type=model)
    
    print("\n--- FINAL ASSEMBLED IDF PREVIEW (first 1000 chars) ---")
    print(final_idf[:1000])
    
    print("\n--- FINAL ASSEMBLED IDF PREVIEW (last 1000 chars) ---")
    print(final_idf[-1000:])
    
if __name__ == "__main__":
    run_test()
