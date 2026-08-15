from sentence_transformers import SentenceTransformer


MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


def main():
    model = SentenceTransformer(MODEL_NAME)

    text = "我们项目里的吞吐量是怎么定义的？"

    embedding = model.encode(text)

    print(f"Text: {text}")
    print(f"Embedding Type: {type(embedding)}")
    print(f"Embedding Shape: {embedding.shape}")
    print()
    print("First 10 values:")
    print(embedding[:10])


if __name__ == "__main__":
    main()