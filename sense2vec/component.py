from typing import Tuple, Union, List
from spacy.tokens import Doc, Token, Span
from spacy.vocab import Vocab
from spacy.language import Language
from pathlib import Path
import numpy

from .sense2vec import Sense2Vec
from .util import merge_phrases, get_phrases, make_spacy_key


class Sense2VecComponent(object):
    name = "sense2vec"

    def __init__(
        self,
        vocab: Vocab = None,
        shape: Tuple[int, int] = (1000, 128),
        merge_phrases: bool = False,
        **kwargs,
    ):
        """Initialize the pipeline component.

        vocab (Vocab): The shared vocab. Mostly used for the shared StringStore.
        shape (tuple): The vector shape.
        merge_phrases (bool): Merge sense2vec phrases into one token.
        RETURNS (Sense2VecComponent): The newly constructed object.
        """
        strings = vocab.strings if vocab is not None else None
        self.s2v = Sense2Vec(shape=shape, strings=strings)
        self.first_run = True
        self.merge_phrases = merge_phrases

    @classmethod
    def from_nlp(cls, nlp: Language, **kwargs):
        """Initialize the component from an nlp object. Mostly used as the
        component factory for the entry point (see setup.py).

        nlp (Language): The nlp object.
        RETURNS (Sense2VecComponent): The newly constructed object.
        """
        return cls(vocab=nlp.vocab, **kwargs)

    def __call__(self, doc: Doc) -> Doc:
        """Process a Doc object with the component.

        doc (Doc): The document to process.
        RETURNS (Doc): The processed document.
        """
        if self.first_run:
            self.init_component()
            self.first_run = False
        # Store reference to s2v object on Doc to make sure it's right
        doc._._s2v = self.s2v
        if self.merge_phrases:
            doc = merge_phrases(doc)
        return doc

    def init_component(self):
        """Register the component-specific extension attributes here and only
        if the component is added to the pipeline and used – otherwise, tokens
        will still get the attributes even if the component is only created and
        not added.
        """
        Doc.set_extension("_s2v", default=None)
        Doc.set_extension("s2v_phrases", getter=get_phrases)
        for obj in [Token, Span]:
            obj.set_extension("s2v_key", getter=self.s2v_key)
            obj.set_extension("in_s2v", getter=self.in_s2v)
            obj.set_extension("s2v_vec", getter=self.s2v_vec)
            obj.set_extension("s2v_freq", getter=self.s2v_freq)
            obj.set_extension("s2v_other_senses", getter=self.s2v_other_senses)
            obj.set_extension("s2v_most_similar", method=self.s2v_most_similar)

    def in_s2v(self, obj: Union[Token, Span]) -> bool:
        """Extension attribute getter. Check if a token or span has a vector.

        obj (Token / Span): The object the attribute is called on.
        RETURNS (bool): Whether the key of that object is in the table.
        """
        return self.s2v_key(obj) in obj.doc._._s2v

    def s2v_vec(self, obj: Union[Token, Span]) -> numpy.ndarray:
        """Extension attribute getter. Get the vector for a given object.

        obj (Token / Span): The object the attribute is called on.
        RETURNS (numpy.ndarray): The vector.
        """
        return obj.doc._._s2v[self.s2v_key(obj)]

    def s2v_freq(self, obj: Union[Token, Span]) -> int:
        """Extension attribute getter. Get the frequency for a given object.

        obj (Token / Span): The object the attribute is called on.
        RETURNS (int): The frequency.
        """
        return obj.doc._._s2v.get_freq(self.s2v_key(obj))

    def s2v_key(self, obj: Union[Token, Span]) -> str:
        """Extension attribute getter and helper method. Create a Sense2Vec key
        like "duck|NOUN" from a spaCy object.

        obj (Token / Span): The object to create the key for.
        RETURNS (unicode): The key.
        """
        return make_spacy_key(
            obj, obj.doc._._s2v.make_key, prefer_ents=self.merge_phrases
        )

    def s2v_most_similar(
        self, obj: Union[Token, Span], n: int = 10
    ) -> List[Tuple[Tuple[str, str], float]]:
        """Extension attribute method. Get the most similar entries.

        n (int): The number of similar entries to return.
        RETURNS (list): The most similar entries as a list of
            ((word, sense), score) tuples.
        """
        key = self.s2v_key(obj)
        results = obj.doc._._s2v.most_similar([key], n=n)
        return [(self.s2v.split_key(result), score) for result, score in results]

    def s2v_other_senses(self, obj: Union[Token, Span]) -> List[str]:
        """Extension attribute getter. Get other senses for an object.

        obj (Token / Span): The object the attribute is called on.
        RETURNS (list): A list of other senses.
        """
        key = self.s2v_key(obj)
        return obj._._s2v.get_other_senses(key)

    def to_bytes(self) -> bytes:
        """Serialize the component to a bytestring.

        RETURNS (bytes): The serialized component.
        """
        return self.s2v.to_bytes(exclude=["strings"])

    def from_bytes(self, bytes_data: bytes):
        """Load the component from a bytestring.

        bytes_data (bytes): The data to load.
        RETURNS (Sense2VecComponent): The loaded object.
        """
        self.s2v = Sense2Vec().from_bytes(bytes_data, exclude=["strings"])
        return self

    def to_disk(self, path: Union[str, Path]):
        """Serialize the component to a directory.

        path (unicode / Path): The path to save to.
        """
        self.s2v.to_disk(path, exclude=["strings"])

    def from_disk(self, path: Union[str, Path]):
        """Load the component from a directory.

        path (unicode / Path): The path to load from.
        RETURNS (Sense2VecComponent): The loaded object.
        """
        self.s2v = Sense2Vec().from_disk(path, exclude=["strings"])
        return self
