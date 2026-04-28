# MorAz Python Wrapper Setup

This guide shows how to build **MorAz**, an Azerbaijani morphological analyzer, and use it from Python through Docker.

The goal is to support search preprocessing, especially conservative grammatical suffix normalization for Azerbaijani.

For example, these should often normalize to the same root for BM25/search stability:

```text
quş
quşlar
quşların
quşlara
```

But lexical/derivational forms should usually stay unchanged:

```text
südlü
yağlı
balıqçı
duzsuz
karbonatlaşmış
```

## Requirements

You need:

```text
Docker
Python 3 on host machine
Internet access to clone MorAz
```

You do not need to install HFST directly on your host if you use Docker.

## 1. Start Docker container

```bash
docker run -it --name moraz-hfst ubuntu:22.04 bash
```

This opens a shell inside the container.

## 2. Install dependencies inside container

```bash
apt-get update
apt-get install -y git make gcc g++ hfst python3
```

## 3. Clone and build MorAz

```bash
git clone https://github.com/berkeozenc/MorAz.git
cd MorAz
make
```

After build, check generated files:

```bash
ls -la
```

You should see files like:

```text
az.inv.hfst
az.inv.ol
az.ol
```

The analyzer file used for lookup is:

```text
/MorAz/az.inv.hfst
```

## 4. Test MorAz manually

Inside the container:

```bash
printf "quşların\n" | hfst-lookup ./az.inv.hfst
```

Expected output should include an analysis like:

```text
quşların    quş<NOM><Num:Pl><Poss:No><Case:Gen>    0.000000
```

Test multiple words:

```bash
cat > test_words.txt <<'EOF'
balığın
güllər
güllərin
kağızlar
məhsullar
süddən
hazırlanmış
suların
sular
karbonatlaşmış
EOF

cat test_words.txt | hfst-lookup ./az.inv.hfst
```

## 5. Keep or restart the container

You can exit the container:

```bash
exit
```

Start it again later:

```bash
docker start moraz-hfst
```

Check containers:

```bash
docker ps -a
```

## 6. How Python calls MorAz

The Python wrapper does not use HTTP.

It calls MorAz through Docker using:

```bash
docker exec -i moraz-hfst hfst-lookup /MorAz/az.inv.hfst
```

and sends words through standard input.

This shell command:

```bash
printf "quşların\nsuların\n" | docker exec -i moraz-hfst hfst-lookup /MorAz/az.inv.hfst
```

is equivalent to what the Python wrapper does internally.

## 7. Add the Python wrapper

Add a Python file to your project, for example:

```text
moraz_client.py
```

The wrapper should:

```text
call docker exec
send words to hfst-lookup through stdin
capture stdout
parse MorAz analyses
extract lemmas
apply conservative normalization rules
```

Recommended import usage:

```python
from moraz_client import MorAzClient

moraz = MorAzClient(container_name="moraz-hfst")

print(moraz.normalize_word("quşların"))
print(moraz.normalize_text("balığın güllərin məhsulları"))
```

## 8. Recommended conservative logic

MorAz may return multiple analyses for one word.

Example:

```text
quşların -> quş<NOM><Num:Pl><Poss:2s><Case:Nom>
quşların -> quş<NOM><Num:Pl><Poss:No><Case:Gen>
```

Both share the same lemma:

```text
quş
```

So it is safe to normalize:

```text
quşların -> quş
```

Recommended rule:

```text
If MorAz returns no analyses:
    keep original word

If all analyses share the same lemma:
    return that lemma

If analyses have different lemmas:
    keep original word
```

## 9. Protect lexical suffixes

For product/category search, do not blindly collapse words with lexical or derivational suffixes.

Usually protect endings like:

```text
-lı, -li, -lu, -lü
-sız, -siz, -suz, -süz
-çı, -çi, -çu, -çü
-lıq, -lik, -luq, -lük
-laş, -ləş
-lan, -lən
```

Examples that should usually stay unchanged:

```text
südlü
yağlı
balıqçı
duzsuz
karbonatlaşmış
```

## 10. Recommended search usage

Do not replace your original text.

Index both:

```text
text_original
text_normalized
```

Example:

```text
text_original:   quşların və güllərin məhsulları
text_normalized: quş və gül məhsul
```

Then retrieve using both fields:

```text
BM25(text_original) + BM25(text_normalized)
```

This improves stability for grammatical variants while preserving exact original wording.

## 11. Expected normalization behavior

Good grammatical normalizations:

```text
balığın        -> balıq
güllər         -> gül
güllərin       -> gül
kağızlar       -> kağız
məhsullar      -> məhsul
süddən         -> süd
suların        -> su
sular          -> su
```

Usually preserve lexical/derived forms:

```text
hazırlanmış        -> hazırlanmış
karbonatlaşmış     -> karbonatlaşmış
südlü              -> südlü
yağlı              -> yağlı
balıqçı            -> balıqçı
duzsuz             -> duzsuz
```

Actual output may vary depending on MorAz analyses and your wrapper rules.

## 12. Troubleshooting

### Container not found

If you see:

```text
No such container: moraz-hfst
```

check container names:

```bash
docker ps -a
```

Then use the correct name in your wrapper.

### Analyzer file not found

Enter the container:

```bash
docker exec -it moraz-hfst bash
```

Check files:

```bash
ls -la /MorAz
```

If `az.inv.hfst` is missing:

```bash
cd /MorAz
make
```

### Docker call is slow

`docker exec` has overhead.

For small tests, this is fine.

For indexing many documents:

```text
batch words/texts
avoid calling normalize_word one by one for millions of tokens
prefer normalize_text or batch methods
```

### Some words are not normalized

This can happen when:

```text
MorAz does not know the word
MorAz returns conflicting analyses
the word has a protected lexical suffix
the word is too ambiguous
```

This is intentional for conservative search normalization. It is usually safer to under-normalize than to over-normalize.
