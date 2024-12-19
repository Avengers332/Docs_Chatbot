import os
import numpy as np
from PIL import Image
from langchain import HuggingFaceHub
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from sklearn.metrics.pairwise import cosine_similarity
import random
import re

# Updated response dictionary with a focus on conversational flow
CASUAL_RESPONSES = {
    "greetings": [
        "hi", "hello", "how are you", "hey", "what's up", "greetings", "good morning", 
        "good afternoon", "good evening", "yo", "hiya", "howdy", "sup", "hey there"
    ],
    "responses": [
        "Hey there! What can I do for you today?",
        "Hi! Need a hand with anything?",
        "Hello! What's on your mind?",
        "Hey! How’s it going? Got any questions?",
        "Good to see you! How can I make your day easier?",
        "Hi! How’s everything going? I'm here to help!",
        "Hello! Ready to tackle something together?"
    ],
    "jokes": [
        "Why did the developer go broke? Because he used up all his cache!",
        "Why do Java developers wear glasses? Because they don't C#!",
        "Why was the JavaScript developer sad? Because he couldn’t ‘null’ his feelings.",
        "How many programmers does it take to change a light bulb? None—it’s a hardware problem!",
        "I told my computer I needed a break, and it sent me a Kit-Kat meme!",
        "Why do programmers prefer dark mode? Because light attracts bugs!",
        "Why don’t programmers like nature? It has too many bugs."
    ],
    "follow_ups": [
        "Anything else on your mind?",
        "Let me know if there’s anything else you need!",
        "I'm here if you have more questions!",
        "Got something else you'd like help with?",
        "Happy to assist! Just let me know."
    ]
}

# Constants
VECTOR_DB_FOLDER = 'data/vector_db'
embedding_function = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
chroma_db = Chroma(persist_directory=VECTOR_DB_FOLDER, embedding_function=embedding_function)
retriever = chroma_db.as_retriever(search_kwargs={"k": 3})

# Load images from folder
def load_images_from_folder(folder_path):
    all_images = []
    for filename in os.listdir(folder_path):
        if filename.endswith((".jpg", ".jpeg", ".png")):
            image_path = os.path.join(folder_path, filename)
            img = Image.open(image_path)
            page_num, source = extract_page_and_source(filename)
            all_images.append({"page": page_num, "source": source, "image": img, "format": img.format.lower()})
    return all_images

# Extract metadata (page number and source) from image filenames
def extract_page_and_source(filename):
    parts = filename.split('_')
    page_num = int(parts[1].replace('page', ''))
    source = parts[2].replace('.jpg', '').replace('.jpeg', '').replace('.png', '')
    return page_num, source


def get_natural_response(query):
    query_lower = query.lower().strip()

    if any(greeting in query_lower for greeting in CASUAL_RESPONSES["greetings"]):

        response = random.choice(CASUAL_RESPONSES["responses"])
        if random.random() < 0.3:  # 30% chance to add a follow-up
            response += " " + random.choice(CASUAL_RESPONSES["follow_ups"])
        return  { "answer" : response}

    
    if "joke" in query_lower or "make me laugh" in query_lower:
        return { "answer" : random.choice(CASUAL_RESPONSES["jokes"])}

    # Default fallback response
    return  { "answer" : "I'm here for you! Just let me know how I can help."}

# Process query and return response
def process_query_and_get_response(query, chain, llm, all_images):
    response = chain.run(query)
    refinement_prompt = f"""
    Please refine the following response to ensure it is a complete, coherent, and well-formed sentence or paragraph. Ensure there is no abrupt or incomplete ending, and make it more natural:
    {response}
    """

    # Refine the response using the LLM
    refined_response = llm(refinement_prompt)
    if "Helpful Answer:" in response:

        start_index = response.index("Helpful Answer:") + len("Helpful Answer:")
        remaining_response = response[start_index:].strip()

        end_index = remaining_response.find("Helpful Answer:")
        if end_index != -1:
            answer = remaining_response[:end_index].strip()
        else:
            answer = remaining_response
        return {'answer' : answer}
    else:
        return {'answer' : response}

    return {'answer' : response}
    refined_response = llm(f"""
    Given the following query and response, please improve the response to make it clearer, more informative, and concise. 
    Focus on improving its quality, coherence, and readability while staying true to the original context.
    Do not repeat the query or response in the output. Avoid adding new information or making assumptions.
    If no relevant information is found in the vector database, provide the response: 
    "Unfortunately, I couldn't find relevant information. Could you provide more context or ask questions related to your documents?"                       
    Return only the improved response, with no extra explanation, marked between 'START' and 'END'.

    Query: '{query}'
    Response: '{response}'

    START
    {{
    <Insert your refined response here. The model will generate this automatically.>
    }}
    END
    """)

    end_response = refined_response.split("START")[-1].split("END")[0].strip()
    if end_response == "{\n    <Insert your refined response here. The model will generate this automatically.>\n    }":
        final_response = "Unfortunately, I couldn't find any relevant information for your query. Please provide more context or ask a query related to your documents."
    else:
        final_response = end_response
    return {"answer": final_response}
    helpful_answers = []
    while "Helpful Answer:" in refined_response:
        start_index = refined_response.index("Helpful Answer:") + len("Helpful Answer:")
        remaining_response = refined_response[start_index:].strip()

        end_index = remaining_response.find("Question:")
        helpful_answers.append(remaining_response[:end_index].strip() if end_index != -1 else remaining_response.strip())
        refined_response = remaining_response[end_index:] if end_index != -1 else ""

    query_embedding = np.array(embedding_function.embed_query(query)).reshape(1, -1)
    best_answer, best_score = None, -1
    for answer in helpful_answers:
        answer_embedding = np.array(embedding_function.embed_documents([answer])[0]).reshape(1, -1)
        score = cosine_similarity(query_embedding, answer_embedding)[0][0]
        if score > best_score:
            best_score = score
            best_answer = answer

    text_results, image_results = retrieve_text_and_images(query, all_images)
    resized_images = [{"page": img["page"], "source": img["source"], "image": img["image"].resize((600, 300))} for img in image_results[:1]]

    return {"answer": refined_response, "images": resized_images}

# Retrieve matching text and images
def retrieve_text_and_images(query, all_images):
    results = retriever.get_relevant_documents(query)
    relevant_images = [
        img for result in results
        for img in all_images if img["page"] == result.metadata["page"] and img["source"] == result.metadata["source"]
    ]
    return results, relevant_images
