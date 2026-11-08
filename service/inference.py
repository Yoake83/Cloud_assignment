"""Load a causal LM + tokenizer from a directory (or Hugging Face id) and generate the JSON text."""
import threading

from promptfmt import build_prompt


class Student:
    def __init__(self, path):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        torch.set_num_threads(1)  # the pod has a CPU limit of 1 core
        self._torch = torch
        self.tok = AutoTokenizer.from_pretrained(path)
        if self.tok.pad_token_id is None:
            self.tok.pad_token = self.tok.eos_token
        self.model = AutoModelForCausalLM.from_pretrained(path, torch_dtype=torch.float32)
        self.model.eval()
        self._lock = threading.Lock()

    def generate(self, text, max_new_tokens=80):
        enc = self.tok(build_prompt(text), return_tensors="pt")
        with self._lock, self._torch.inference_mode():
            out = self.model.generate(
                **enc, max_new_tokens=max_new_tokens, do_sample=False,
                eos_token_id=self.tok.eos_token_id, pad_token_id=self.tok.pad_token_id,
            )
        new_tokens = out[0, enc["input_ids"].shape[1]:]
        decoded = self.tok.decode(new_tokens, skip_special_tokens=True)
        stripped = decoded.strip()
        return stripped.splitlines()[0] if stripped else ""
