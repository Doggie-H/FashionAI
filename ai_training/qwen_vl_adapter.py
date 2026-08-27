import os
from pathlib import Path


_TRUE = {"1", "true", "yes", "on"}


class Qwen25VLAdapter:
    """Lazy, resource-bounded Qwen2.5-VL adapter for local inference."""

    def __init__(self, model_id=None, model_revision=None):
        self.model_id = model_id or os.getenv("QWEN_VL_MODEL_ID", "Qwen/Qwen2.5-VL-7B-Instruct")
        self.model_revision = model_revision or os.getenv("QWEN_VL_MODEL_REVISION")
        self.min_pixels = int(os.getenv("QWEN_VL_MIN_PIXELS", 256 * 28 * 28))
        self.max_pixels = int(os.getenv("QWEN_VL_MAX_PIXELS", 768 * 28 * 28))
        self.max_new_tokens = int(os.getenv("QWEN_VL_MAX_NEW_TOKENS", "160"))
        self.quantization = os.getenv("QWEN_VL_QUANTIZATION", "none").lower()
        self.use_flash_attention = os.getenv("QWEN_VL_USE_FLASH_ATTN", "0").lower() in _TRUE
        self.trust_remote_code = os.getenv("QWEN_VL_TRUST_REMOTE_CODE", "0").lower() in _TRUE
        self.processor = None
        self.model = None
        self.is_loaded = False

    def load_model(self):
        if self.is_loaded:
            return
        import torch
        from transformers import AutoProcessor, Qwen2_5_VLForConditionalGeneration

        has_cuda = torch.cuda.is_available()
        dtype = torch.float16 if has_cuda else torch.float32
        revision_kwargs = {"revision": self.model_revision} if self.model_revision else {}
        self.processor = AutoProcessor.from_pretrained(
            self.model_id,
            min_pixels=self.min_pixels,
            max_pixels=self.max_pixels,
            trust_remote_code=self.trust_remote_code,
            **revision_kwargs,
        )
        model_kwargs = {
            "torch_dtype": dtype,
            "device_map": os.getenv("QWEN_VL_DEVICE_MAP", "auto"),
            "low_cpu_mem_usage": True,
            "trust_remote_code": self.trust_remote_code,
        }
        if self.quantization in {"4bit", "8bit"}:
            from transformers import BitsAndBytesConfig
            model_kwargs["quantization_config"] = BitsAndBytesConfig(
                load_in_4bit=self.quantization == "4bit",
                load_in_8bit=self.quantization == "8bit",
                bnb_4bit_compute_dtype=torch.float16 if has_cuda else torch.float32,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_use_double_quant=True,
            )
        if self.use_flash_attention and has_cuda:
            model_kwargs["attn_implementation"] = "flash_attention_2"
        self.model = Qwen2_5_VLForConditionalGeneration.from_pretrained(self.model_id, **revision_kwargs, **model_kwargs)
        self.model.eval()
        self.is_loaded = True

    def _generate_json(self, image_path: str, instruction: str) -> str:
        if not self.is_loaded:
            raise RuntimeError("Qwen2.5-VL is not loaded")
        import torch
        from qwen_vl_utils import process_vision_info

        image_uri = Path(image_path).resolve().as_uri()
        messages = [{
            "role": "user",
            "content": [
                {"type": "image", "image": image_uri},
                {"type": "text", "text": instruction},
            ],
        }]
        text = self.processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        image_inputs, video_inputs = process_vision_info(messages)
        inputs = self.processor(
            text=[text], images=image_inputs, videos=video_inputs,
            padding=True, return_tensors="pt",
        )
        target_device = next(self.model.parameters()).device
        inputs = {key: value.to(target_device) if hasattr(value, "to") else value for key, value in inputs.items()}
        with torch.inference_mode():
            generated_ids = self.model.generate(
                **inputs,
                max_new_tokens=self.max_new_tokens,
                do_sample=False,
                num_beams=1,
                use_cache=True,
            )
        trimmed_ids = [out[len(inp):] for inp, out in zip(inputs["input_ids"], generated_ids)]
        return self.processor.batch_decode(trimmed_ids, skip_special_tokens=True)[0].strip()

    def describe_image(self, image_path: str) -> str:
        return self._generate_json(
            image_path,
            """Analyze this clothing item. Return JSON only with exactly these keys: """
            "item_category, materials, visual_tier, base_style, key_details. "
            "Do not invent details that are not visible.",
        )

    def analyze_garment_for_styling(self, image_path: str) -> str:
        return self._generate_json(
            image_path,
            """Analyze one visible clothing item only. Return compact JSON with exactly these keys:
            category, styles, occasions, seasons, color_family, material, silhouette,
            formality_level, statement_level, weather_suitability, mobility_support,
            modesty_level,             intent_support, pairing_hints, avoid_pairing_with, structural_profile, structural_evidence,
            confidence, rationales, limitations.

            Use only these taxonomy values. category: top|bottom|dress|outerwear|footwear|belt|accessory.
            styles: minimal|classic|smart_casual|streetwear|romantic|business|sporty|quiet_luxury|preppy|edgy|bohemian|athleisure|utility|modest|resort|creative|vintage.
            occasions: daily|work|date|event|travel|formal|interview|meeting|presentation|celebration|weekend|gym|outdoor|home|cocktail|wedding_guest.
            seasons: spring|summer|autumn|winter|all_season. color_family: neutral|black|white|navy|earth|burgundy|emerald|bright.
            formality_level: casual|smart_casual|business|formal|ceremonial. statement_level: subtle|balanced|statement.
            weather_suitability: hot|mild|cold|rainy|humid. mobility_support: low|normal|high. modesty_level: standard|covered|conservative.
            intent_support: comfort|all_day|weather_protection|photo_ready|low_maintenance|packable|movement|coverage|professional_presence|celebration|confidence.
            pairing_hints and avoid_pairing_with must use the styles vocabulary. confidence and rationales must be JSON objects keyed by the supplied dimensions.
            structural_profile must be an object with source_views and these closed fields: neckline (crew|v_neck|round|collar|polo|halter|strapless|unknown), shoulder_construction (set_in|dropped|raglan|sleeveless|unknown), shoulder_width (narrow|regular|wide|unknown), sleeve_length (sleeveless|cap|short|elbow|long|unknown), torso_length (cropped|waist|hip|long|unknown), waist_shape (fitted|regular|relaxed|peplum|unknown), hem_shape (straight|curved|asymmetric|unknown), rise (low|mid|high|unknown), waist_construction (flat|elastic|belted|unknown), hip_fit (fitted|regular|relaxed|unknown), leg_shape (skinny|slim|straight|tapered|wide|bootcut|flared|unknown), leg_length (short|cropped|ankle|full|unknown). structural_evidence must be an array of objects with feature, value, confidence, visible_views, rationale for only visible cues.
            Use only visually supportable claims. Put unknown, hidden construction, fabric behavior, exact size, unseen details, measurements, back panels and physical fit in limitations; do not invent them.""",
        )

    def detect_user_profile(self, image_path: str) -> str:
        return self._generate_json(
            image_path,
            """Analyze the visible person and return JSON only with exactly these keys: """
            "body_type, skin_tone, hair_type, face_shape, body_proportions. "
            "Choose conservative values and state uncertainty inside the values when needed.",
        )
