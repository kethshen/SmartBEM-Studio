import sys
import os

# Adjust path to find backend modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.prompt_structurer import PromptStructurer

def test_multizone_structuring():
    print("=== Testing Multi-Zone Prompt Structuring ===")
    raw_prompt = (
        "Simulate a building with three zones: an office, a meeting room, a lobby. "
        "The office is 6.00 meters long, 8.00 meters wide, and 4.00 meters high. The meeting room is attached to the North wall of the office. "
        "The meeting room is 6.00 meters long, 4.00 meters wide, and 4.00 meters high. The lobby is attached to the East wall of the office. "
        "The lobby is 5.00 meters long, 8.00 meters wide, and 4.00 meters high. "
        "For the office: place a 1.5x2m window on the South wall 2m from left edge, 1m from top edge. place a 0.8x1.5m window on the West wall 2m from left edge, 1.5m from top edge. place a 1x2.5m door on the West wall 5m from left edge, fix to ground. Make the South wall out of 'M01 100mm brick' and 'I02 50mm insulation board' and the other walls out of 'Medium Exterior Wall'. "
        "For the meeting room: place a 1x1m window on the North wall 2m from left edge, 1.5m from top edge. place a 0.8x1.5m window on the West wall 1m from left edge, 1.5m from top edge. place a 1x2.5m door on the South wall 0.5m from left edge, fix to ground. Make the North wall out of 'M01 100mm brick' and 'I02 50mm insulation board' and the other walls out of 'Medium Exterior Wall'. "
        "For the lobby: place a 2x2.5m door on the East wall 3m from left edge, fix to ground. place a 1x2.5m door on the South wall 2m from left edge, fix to ground. place a 1x1.5m window on the South wall 4.5m from left edge, 1.5m from top edge. Make the South wall out of 'M01 100mm brick' and 'I02 50mm insulation board' and the other walls out of 'Medium Exterior Wall'. "
        "All three zone has pitched roofs with a gable height of 3 meters. Place a 2.0x1.5m skylight on the roof. "
        "The occupancy rate is 30.00 m2/people, the lighting level is 6.00 W/m2, and the equipment power consumption is 45.80 W/m2. "
        "All zones use a packaged AC unit (psz_ac). "
        "People are in the building from 9am to 5pm on weekdays and completely closed on weekends. "
        "The lights are on from 8am to 6pm, and the equipment runs 24/7."
    )
    
    structurer = PromptStructurer()
    # Call with model_type='ollama' (using fallback direct ollama import)
    try:
        structured = structurer.restructure_prompt(raw_prompt, model_type="ollama")
        print("\n[RESULT]\n")
        print(structured)
        print("\n============================================\n")
        assert "[GLOBAL SETTINGS]" in structured, "Missing global settings block"
        assert "<Zone: Office>" in structured, "Missing Office zone block"
        assert "<Zone: MeetingRoom>" in structured, "Missing MeetingRoom zone block"
        assert "<Zone: Lobby>" in structured, "Missing Lobby zone block"
        print("[SUCCESS] Multi-Zone prompt successfully structured!")
    except Exception as e:
        print(f"[FAIL] Multi-Zone test failed: {e}")

def test_singlezone_structuring():
    print("=== Testing Single-Zone Prompt Structuring ===")
    raw_prompt = (
        "Create a standalone shop zone, 10 meters wide and 10 meters long and 3 meters high. "
        "Place a door of size 1x2.2m on the South wall 4m from left, and a window of size 1.5x1.5m on the South wall 1.5m from left. "
        "The wall construction should be 'Medium Exterior Wall'."
    )
    
    structurer = PromptStructurer()
    try:
        structured = structurer.restructure_prompt(raw_prompt, model_type="ollama")
        print("\n[RESULT]\n")
        print(structured)
        print("\n============================================\n")
        assert "[GLOBAL SETTINGS]" in structured, "Missing global settings block"
        assert "<Zone:" in structured, "Missing Zone tags"
        print("[SUCCESS] Single-Zone prompt successfully structured!")
    except Exception as e:
        print(f"[FAIL] Single-Zone test failed: {e}")

if __name__ == "__main__":
    test_multizone_structuring()
    print()
    test_singlezone_structuring()
