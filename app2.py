doc = nlp("La fusée a décollé de la Terre vers la Lune.")
for token in doc:
    print(token.text, token.dep_, token.head.text, token.pos_, token.head.pos_)
