import json

def analyze_model(name, filename):
    with open(filename, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    refusal_count = 0
    bullet_lists = 0
    total_len = 0
    times = []
    
    refusal_phrases = [
        "I don't have specific information", 
        "I'm sorry", 
        "I cannot answer",
        "does not mention",
        "not provided in the sources"
    ]
    
    for item in data:
        ans = item['answer']
        total_len += len(ans)
        
        # Check if model politely refused or gracefully admitted lack of knowledge
        if any(phrase.lower() in ans.lower() for phrase in refusal_phrases):
            refusal_count += 1
            
        # Check formatting complexity
        if "-" in ans or "*" in ans or "\n1." in ans:
            bullet_lists += 1
            
        times.append(item['time'])
        
    print(f"=== {name} ===")
    print(f"Total Questions: {len(data)}")
    print(f"Polite Unknowns / Refusals: {refusal_count}")
    print(f"Bullet/Formatted Responses: {bullet_lists}")
    log_content += f"Avg Response Length (Chars): {total_len / len(data):.0f}\n"
    if times:
        log_content += f"Avg Time: {sum(times)/len(times):.2f}s\n"
    log_content += "\n"
    return data

llama = analyze_model("Llama 3.2 (3B)", "test_results/full_llama3.2_3b_20260329_1505.json")
try:
    gemma = analyze_model("Gemma 3 (4B)", "test_results/full_gemma3_4b_20260329_1505.json")
except Exception as e:
    log_content += f"Error opening gemma: {e}\n"
    gemma = llama

log_content += "\n=== Direct Quality Comparison (Sample) ===\n"
indices = [0, 45, 90, 150, 200]
for i in indices:
    if i < len(llama):
        log_content += f"Q: {llama[i]['question']}\n"
        log_content += f"Llama: {llama[i]['answer'][:200]}...\n"
        log_content += f"Gemma: {gemma[i]['answer'][:200]}...\n"
        log_content += "-" * 50 + "\n"

with open("analyze_out.txt", "w", encoding="utf-8") as file:
    file.write(log_content)
