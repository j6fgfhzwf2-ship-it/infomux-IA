from llama_cpp import Llama

# Charge ton modèle local GGUF
llm = Llama(
    model_path="models/your-model.gguf",
    n_ctx=4096,
    n_threads=6,     # adapte selon ton CPU
    n_gpu_layers=0   # 0 = CPU only, >0 = si tu veux activer GPU
)

def generate_llama(prompt: str, max_tokens=256):
    output = llm(
        prompt,
        max_tokens=max_tokens,
        temperature=0.7,
        top_p=0.9,
        echo=False
    )
    return output["choices"][0]["text"]

