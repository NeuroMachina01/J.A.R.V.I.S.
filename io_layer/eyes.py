# io/eyes.py
# Screen capture → Gemini Vision → structured problem description.
# Eyes describe. Brain decides. They never overlap.

import base64
import logging
from dataclasses import dataclass
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage

logger = logging.getLogger(__name__)

VISION_SYSTEM_PROMPT = """You are JARVIS's visual cortex. Your job is to analyze the provided image (which is a live screenshot of the user's screen) and describe it precisely.

CRITICAL INSTRUCTION: You are a multimodal AI. You CAN see the image provided. NEVER reply with "I cannot see the image", "I do not have access to the screen", or "I am a text-based AI". 

Your output is consumed by JARVIS's logic brain, so it MUST be highly structured.

Always respond in this exact format:
CONTENT_TYPE: <code_error | math_problem | diagram | text | ui | terminal | other>
DESCRIPTION: <one clear, highly detailed sentence describing what is visible>
PROBLEM: <the exact problem, question, or error shown — be precise and extract exact text/numbers>
CONTEXT: <any surrounding code, text, or UI elements that help understand the problem>
CONFIDENCE: <high | medium | low>

Rules:
- For code errors: extract the exact error message, file name, and line number if visible.
- For math: transcribe the exact mathematical expression.
- For diagrams: describe the structure, nodes, and relationships.
- Never solve the problem yourself — only describe it thoroughly for the solver agent.
- If the screen is entirely blank or unreadable, state 'Screen is blank' honestly, but NEVER claim you lack vision capabilities.
"""


@dataclass
class VisionOutput:
    content_type: str       # code_error | math | diagram | text | ui | terminal | other
    description: str        # one-liner of what's visible
    problem: str            # the specific problem/error/question
    context: str            # surrounding context
    confidence: str         # high | medium | low
    raw_response: str       # full LLM response for debugging


class Eyes:
    def __init__(self):
        # Gemini 2.5 Flash is natively multimodal and exceptionally fast for vision
        self.llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.1)

    def capture(self) -> bytes:
        """
        Captures the full screen.
        Returns raw PNG bytes.
        Requires: pip install mss
        """
        try:
            import mss
            import mss.tools

            with mss.mss() as sct:
                # Capture primary monitor
                monitor = sct.monitors[1]
                screenshot = sct.grab(monitor)
                return mss.tools.to_png(screenshot.rgb, screenshot.size)

        except ImportError:
            raise RuntimeError("Install mss: pip install mss")

    def capture_region(self, x: int, y: int, width: int, height: int) -> bytes:
        """Capture a specific screen region instead of full screen."""
        try:
            import mss
            import mss.tools

            with mss.mss() as sct:
                region = {"top": y, "left": x, "width": width, "height": height}
                screenshot = sct.grab(region)
                return mss.tools.to_png(screenshot.rgb, screenshot.size)

        except ImportError:
            raise RuntimeError("Install mss: pip install mss")

    def describe(self, image_bytes: bytes) -> VisionOutput:
        """
        Sends screen capture to Gemini Vision.
        """
        image_b64 = base64.standard_b64encode(image_bytes).decode("utf-8")

        try:
            # Construct the multimodal message for LangChain
            messages = [
                SystemMessage(content=VISION_SYSTEM_PROMPT),
                HumanMessage(
                    content=[
                        {
                            "type": "text", 
                            "text": "Describe what you see on this screen."
                        },
                        {
                            "type": "image_url", 
                            "image_url": f"data:image/png;base64,{image_b64}"
                        }
                    ]
                )
            ]

            response = self.llm.invoke(messages)
            raw = response.content
            
            return self._parse_response(raw)

        except Exception as e:
            logger.error(f"Vision LLM call failed: {e}")
            return VisionOutput(
                content_type="other",
                description="Vision processing failed",
                problem="",
                context="",
                confidence="low",
                raw_response=str(e),
            )

    def see_and_describe(self) -> VisionOutput:
        """
        Convenience method: capture screen + describe in one call.
        This is what Brain calls when vision trigger fires.
        """
        logger.info("Eyes: capturing screen...")
        image_bytes = self.capture()
        logger.info("Eyes: sending to Vision LLM...")
        result = self.describe(image_bytes)
        logger.info(f"Eyes: detected {result.content_type} (confidence: {result.confidence})")
        return result

    def _parse_response(self, raw: str) -> VisionOutput:
        """Parse the structured Vision LLM response into VisionOutput."""
        fields = {
            "content_type": "other",
            "description": "",
            "problem": "",
            "context": "",
            "confidence": "low",
        }

        for line in raw.strip().split("\n"):
            if ":" in line:
                key, _, value = line.partition(":")
                key = key.strip().lower().replace(" ", "_")
                value = value.strip()
                if key in fields:
                    fields[key] = value

        return VisionOutput(**fields, raw_response=raw)

    def build_description_string(self, output: VisionOutput) -> str:
        """
        Converts VisionOutput into a single string for the router/brain.
        This is what gets injected into AgentInput.vision_description.
        """
        parts = [f"Type: {output.content_type}"]
        if output.description:
            parts.append(f"Description: {output.description}")
        if output.problem:
            parts.append(f"Problem: {output.problem}")
        if output.context:
            parts.append(f"Context: {output.context}")
        return " | ".join(parts)
