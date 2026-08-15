from sentence_transformers import SentenceTransformer
from sentence_transformers.util import cos_sim


MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


def main():
    model = SentenceTransformer(MODEL_NAME)

    query = "我们项目里的吞吐量是怎么定义的？"

    throughput_text = """
    throughput

    Definition:

    The cumulative number of vehicles that arrived at their destination
    during the simulation observation window.

    Unit:

    veh
    """

    queue_text = """
    average_queue

    Definition:

    At each simulation step, sum the number of halting vehicles over all
    monitored approach lanes. Then average this total queue over all
    simulation steps.
    """

    query_embedding = model.encode(query)
    throughput_embedding = model.encode(throughput_text)
    queue_embedding = model.encode(queue_text)

    throughput_similarity = cos_sim(
        query_embedding,
        throughput_embedding,
    ).item()

    queue_similarity = cos_sim(
        query_embedding,
        queue_embedding,
    ).item()

    print(f"Query: {query}")
    print()

    print("Similarity with throughput:")
    print(throughput_similarity)
    print()

    print("Similarity with average_queue:")
    print(queue_similarity)


if __name__ == "__main__":
    main()