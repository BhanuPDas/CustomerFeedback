import json
import logging
from transformers import T5Tokenizer, T5ForConditionalGeneration

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

# Load T5 model and tokenizer
tokenizer = T5Tokenizer.from_pretrained("t5-small")
model = T5ForConditionalGeneration.from_pretrained("t5-small")


def paraphrase_text(text, num_return_sequences=3):
    """Generate paraphrases for a given text."""
    input_text = f"{text} </s>"
    input_ids = tokenizer.encode(input_text, return_tensors="pt", max_length=512, truncation=True)

    outputs = model.generate(
        input_ids=input_ids,
        max_length=256,  # Limiting output length to 256 tokens
        num_return_sequences=num_return_sequences,
        num_beams=1,
        temperature=1.7,
        top_k=40,
        top_p=0.85,
        do_sample=True
    )
    return [tokenizer.decode(output, skip_special_tokens=True, clean_up_tokenization_spaces=True) for output in outputs]

# Start logging
logging.info(f"Started processing feedback data.")

# Load JSON feedback data
input_file = 'feedback_input_text_descriptive.json'
output_file = 'feedback_input_text_unique_variations.json'

with open(input_file, 'r') as file:
    feedback_data = json.load(file)
    
logging.info(f"Loaded {len(feedback_data)} feedback entries.")

# Generate unique feedback
unique_feedback_data = []
seen_texts = set()

for idx, feedback in enumerate(feedback_data):
    if idx % 500 == 0:  # Log progress every 500 entries
        logging.info(f"Processing feedback {idx + 1}/{len(feedback_data)}")
    original_text = feedback["text"]
    paraphrases = paraphrase_text(original_text, num_return_sequences=5)
    
    unique_paraphrases = []  # Initialize the list to store unique paraphrases
    
    for paraphrase in paraphrases:
        if paraphrase not in seen_texts and len(unique_paraphrases) < 3:
            seen_texts.add(paraphrase)
            unique_paraphrases.append(paraphrase)
        if len(unique_paraphrases) >= 3:  # Stop once 3 unique paraphrases are found
            break

    # Add the 3 unique paraphrases to the result
    for unique_paraphrase in unique_paraphrases:
        unique_feedback_data.append({"text": unique_paraphrase, "stars": feedback["stars"]})  

# Save the updated feedback
with open(output_file, 'w') as outfile:
    json.dump(unique_feedback_data, outfile, indent=4)

logging.info(f"Unique paraphrased feedback saved to {output_file}")
