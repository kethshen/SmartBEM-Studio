import os
import json
import openai
from google import genai 
from huggingface_hub import InferenceClient

class AIPipelines:
    def __init__(self, secrets_path="secrets.json", template_path="templates/Base.idf"):
        # 1. Load Secrets
        self.api_keys = {}
        if os.path.exists(secrets_path):
            with open(secrets_path, "r") as f:
                self.api_keys = json.load(f)
        else:
            print(f"[AI] Warning: {secrets_path} not found. AI generation will fail.")

        # 2. Configure OpenAI
        if "OPENAI_API_KEY" in self.api_keys:
            try:
                self.openai_client = openai.OpenAI(api_key=self.api_keys["OPENAI_API_KEY"])
            except Exception as e:
                print(f"[AI] Failed to init OpenAI: {e}")
                self.openai_client = None
        else:
            self.openai_client = None

        # 3. Configure Gemini (New SDK)
        if "GEMINI_API_KEY" in self.api_keys:
             try:
                self.gemini_client = genai.Client(api_key=self.api_keys["GEMINI_API_KEY"])
             except Exception as e:
                print(f"[AI] Failed to init Gemini: {e}")
                self.gemini_client = None
        else:
            self.gemini_client = None

        # 3.5 Configure HuggingFace
        if "HUGGINGFACE_API_KEY" in self.api_keys:
            self.hf_api_key = self.api_keys["HUGGINGFACE_API_KEY"]
            try:
                self.hf_client = InferenceClient(api_key=self.hf_api_key)
            except Exception as e:
                print(f"[AI] Failed to init HuggingFace: {e}")
                self.hf_client = None
        else:
            self.hf_api_key = None
            self.hf_client = None

        # 4. Load Base Template
        self.base_idf = ""
        if os.path.exists(template_path):
            with open(template_path, "r") as f:
                self.base_idf = f.read()
        else:
             print(f"[AI] Warning: {template_path} not found. Using empty string.")

    def generate_idf_from_text(self, nlp_text, config, model_type="openai"):
        """
        Generates a modified IDF by requesting JSON from the AI and combining modules.
        """
        print(f"[AI] Generating Modular IDF using model: {model_type}")

        # 1. Load the Menu
        import sys
        # ensure we can import from backend dir
        sys.path.append(os.path.dirname(__file__))
        import geometry_util
        import idf_extractor

        try:
            with open(os.path.join(os.path.dirname(__file__), "index.json"), 'r', encoding='utf-8') as f:
                index_data = json.load(f)
            construction_menu = list(index_data.get("Construction", {}).keys())
        except Exception as e:
            print(f"Warning: Could not load index.json: {e}")
            construction_menu = ["Composite 2x4 Wood Stud R11"]

        # 2. Construct Prompt for JSON
        weather_file = config.get('weather_file', 'Unknown')
        system_prompt = (
            "You are an expert EnergyPlus consultant integrating modular components. "
            "Your task is to analyze the user's natural language request and output a JSON dictionary containing the building parameters.\n"
            "CRITICAL RULES:\n"
            "1. OUTPUT FORMAT: Return ONLY valid JSON. No markdown wrappers, no explanations.\n"
            "2. Required JSON keys: 'length' (float), 'width' (float), 'height' (float), 'wall_construction' (string), 'roof_construction' (string).\n"
            "3. For the construction keys, you MUST pick the closest matching name from this exact menu array:\n"
            f"{construction_menu}\n"
        )

        user_prompt = (
            f"USER TASK: {nlp_text}\n"
            f"CONFIG: {json.dumps(config)}\n\n"
            "OUTPUT ONLY VALID JSON:"
        )

        # 3. Call AI
        try:
            if model_type == "openai":
                json_output = self._call_openai(system_prompt, user_prompt)
            elif model_type == "gemini":
                json_output = self._call_gemini(system_prompt, user_prompt)
            elif model_type == "huggingface":
                json_output = self._call_huggingface(system_prompt, user_prompt)
            else:
                return f"! Error: Unknown model type '{model_type}'"
            
            # Clean possible markdown block
            json_output = json_output.replace("```json", "").replace("```", "").strip()
            
            # 4. Parse AI Parameters
            params = json.loads(json_output)
            L = params.get("length", 10.0)
            W = params.get("width", 10.0)
            H = params.get("height", 3.0)
            wall_name = params.get("wall_construction", "Composite 2x4 Wood Stud R11")
            roof_name = params.get("roof_construction", "Composite 2x4 Wood Stud R11")

            print(f"[AI Assembler] AI Selected -> L:{L}, W:{W}, Wall:{wall_name}")

            # 5. Build Geometry
            geometry_idf = geometry_util.generate_zone_geometry(L, W, H)
            
            # 6. Extract Dependencies
            extracted_blocks = {}
            idf_extractor.resolve_dependencies("Construction", wall_name, extracted_blocks)
            idf_extractor.resolve_dependencies("Construction", roof_name, extracted_blocks)

            # 7. Stitch it all together
            final_idf = self.base_idf + "\n\n"
            for block in extracted_blocks.values():
                final_idf += block + "\n\n"
            
            final_idf += geometry_idf

            # 8. Replace placeholder constructions inside the geometry with the AI's selection
            final_idf = final_idf.replace("{EXTERIOR_WALL_CONSTR}", wall_name)
            final_idf = final_idf.replace("{ROOF_CONSTR}", roof_name)
            final_idf = final_idf.replace("{FLOOR_CONSTR}", wall_name) # Simplified for now

            return final_idf

        except json.JSONDecodeError as je:
             print(f"[AI] Error parsing JSON from AI output: {je}")
             return f"! Error: AI failed to output valid JSON. Result was: {json_output}"
        except Exception as e:
            print(f"[AI] Error generating IDF: {e}")
            return f"! Analysis Error: {str(e)}"

    def _call_openai(self, system, user):
        if not self.openai_client:
            raise ValueError("OpenAI API Key missing or client failed to init.")
            
        response = self.openai_client.chat.completions.create(
            model="gpt-4o", 
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user}
            ],
            temperature=0.2
        )
        content = response.choices[0].message.content
        return self._sanitize_output(content)

    def _call_gemini(self, system, user):
        if not self.gemini_client:
             raise ValueError("Gemini API Key missing or client failed to init.")
            
        # Gemini (New SDK) uses models.generate_content
        full_prompt = f"{system}\n\n{user}"
        response = self.gemini_client.models.generate_content(
            model='gemini-2.5-flash-lite', 
            contents=full_prompt
        )
        return self._sanitize_output(response.text)

    def _call_huggingface(self, system, user):
        if not self.hf_client:
            raise ValueError("HuggingFace Client missing or API Key not provided.")
            
        try:
            response = self.hf_client.chat.completions.create(
                model="meta-llama/Llama-3.1-8B-Instruct",
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user}
                ],
                max_tokens=1500,
                temperature=0.2
            )
            content = response.choices[0].message.content
            return self._sanitize_output(content)
        except Exception as e:
            return f"! Analysis Error: HuggingFace API Exception -> {str(e)}"

    def _sanitize_output(self, text):
        """Removes markdown wrappers if present."""
        clean = text.strip()
        if clean.startswith("```"):
            # Find first newline
            first_newline = clean.find("\n")
            if first_newline != -1:
                clean = clean[first_newline+1:]
        if clean.endswith("```"):
            clean = clean[:-3]
        return clean.strip()

    def test_connections(self, check_openai=True, check_gemini=True, check_hf=True):
        """Tests connectivity to APIs based on flags."""
        results = {"openai": False, "gemini": False, "hf": False, "details": ""}
        
        # Test OpenAI
        if check_openai:
            if self.openai_client:
                try:
                    self.openai_client.chat.completions.create(
                        model="gpt-3.5-turbo", messages=[{"role": "user", "content": "hi"}], max_tokens=1
                    )
                    results["openai"] = True
                except Exception as e:
                    results["details"] += f"OpenAI Fail: {str(e)}; "
            else:
                 results["details"] += "OpenAI Client Missing; "
        else:
             results["details"] += "OpenAI Skipped; "
        
        # Test Gemini
        if check_gemini:
            if self.gemini_client:
                try:
                    self.gemini_client.models.generate_content(
                        model='gemini-2.5-flash-lite', contents="hi"
                    )
                    results["gemini"] = True
                except Exception as e:
                    results["details"] += f"Gemini Fail: {str(e)}; "
            else:
                 results["details"] += "Gemini Client Missing; "
        else:
             results["details"] += "Gemini Skipped; "
             
        # Test HuggingFace
        if check_hf:
            if self.hf_client:
                try:
                    self.hf_client.chat.completions.create(
                        model="meta-llama/Llama-3.1-8B-Instruct",
                        messages=[{"role": "user", "content": "hi"}],
                        max_tokens=1
                    )
                    print("[AI] HuggingFace Test: ✅ Success")
                    results["hf"] = True
                except Exception as e:
                    print(f"[AI] HuggingFace Test Exception ❌: {str(e)}")
                    results["details"] += f"HF Exception: {str(e)}; "
            else:
                print("[AI] HuggingFace Test ❌: Missing API Key or Client Init Failed.")
                results["details"] += "HF Client Missing; "
        else:
            results["details"] += "HF Skipped; "
                
        return results

