from moraz_client import MorAzClient


def main():
    moraz = MorAzClient(container_name="moraz-hfst")

    words = [
        "balığın",
        "güllər",
        "güllərin",
        "kağızlar",
        "məhsullar",
        "süddən",
        "hazırlanmış",
        "suların",
        "sular",
        "karbonatlaşmış",
        "südlü",
        "yağlı",
        "balıqçı",
        "duzsuz",
    ]

    for word in words:
        print(f"{word:20s} -> {moraz.normalize_word(word)}")

    print()
    text = "balığın güllərin kağızlar məhsullar süddən hazırlanmış"
    print("Original:  ", text)
    print("Normalized:", moraz.normalize_text(text))


if __name__ == "__main__":
    main()
