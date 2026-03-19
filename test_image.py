import os
from dotenv import load_dotenv
load_dotenv()
from huggingface_hub import InferenceClient

client = InferenceClient(
    provider="hf-inference",
    api_key=os.environ["HF_TOKEN"],
)

image = client.text_to_image(
    "Astronaut riding a horse",
    model="black-forest-labs/FLUX.1-schnell",
)

image.save("test_output.png")
print("Done: test_output.png")
