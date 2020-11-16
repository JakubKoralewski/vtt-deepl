import math
from copy import copy, deepcopy

from pycaption import WebVTTReader, SRTWriter, Caption, CaptionSet, CaptionNode
from pathlib import Path
from typing import List, Dict


class MyCaption:
	def __init__(self, raw_caption: Caption):
		self.raw_caption = raw_caption
		self.raw_text = raw_caption.get_text()
		self.lines = self.raw_text.split('\n')
		assert len(self.lines) > 0

	def ends_with(self, possibilities: List[str]):
		return any([self.raw_text.endswith(possibility) for possibility in possibilities])


class Sentence:
	caption_separators = [",", ";", ":", " "]
	captions: List[MyCaption]

	def __init__(self):
		self.captions = []

	def append(self, caption: MyCaption):
		self.captions.append(caption)

	def text(self):
		return ' '.join([caption.raw_text.replace('\n', ' ') for caption in self.captions])

	def match_captions_with_estimate(self, orig: str, trans: str) -> Dict[int, str]:
		rv = {}
		original_length = len(orig)
		trans_pos = 0
		trans_len = len(trans)

		def set_rv(index: int, caption_index: int):
			nonlocal trans_pos
			if caption_index == len(self.captions) - 1:
				index = len(trans)
			rv[caption_index] = trans[trans_pos:index+1]
			trans_pos = index + 1

		for caption_index, caption in enumerate(self.captions):
			percent_length = len(caption.raw_text) / original_length
			index_rough_guess = min(trans_len - 1, trans_pos + math.floor(percent_length * trans_len))
			center = trans[index_rough_guess]
			if center in self.caption_separators:
				set_rv(index_rough_guess, caption_index)
			else:
				i = 1
				while True:
					left_index = index_rough_guess - i
					no_more_space = True
					if left_index > 0:
						no_more_space = False
						left = trans[left_index]
						if left in self.caption_separators:
							set_rv(left_index, caption_index)
							break
					right_index = index_rough_guess + i
					if right_index < trans_len:
						no_more_space = False
						right = trans[right_index]
						if right in self.caption_separators:
							set_rv(right_index, caption_index)
							break
					if no_more_space:
						set_rv(trans_len - 1, caption_index)
						break
					i += 1

		return rv


class SentenceManager:
	sentences: List[Sentence]
	sentence_enders = [".", "?", "!"]

	def __init__(self):
		self.sentences = []
		self.cur_sentence = Sentence()

	def add_caption(self, caption: MyCaption):
		"""
		Add capiton which may or may not be a whole sentence
		:param caption:
		:return:
		"""
		self.cur_sentence.append(caption)
		if caption.ends_with(self.sentence_enders):
			self._finish_current()

	def _finish_current(self):
		self.sentences.append(self.cur_sentence)
		self.cur_sentence = Sentence()

	def finish(self):
		"""
		Communicate no more captions coming in so close last one.
		:return:
		"""
		self._finish_current()
		self.cur_sentence = None

	def write_to_file(self, out_file: Path):
		out_file_handle = out_file.open('w+', encoding='UTF-8')
		for sentence in self.sentences:
			out_file_handle.write(sentence.text() + '\n\n')

	def match_translation_from_file(self, original: Path, translated: Path) -> Dict[int, Dict[int, str]]:
		non_empty = lambda x: len(x) > 0
		original = list(filter(non_empty, original.read_text('UTF-8').split('\n')))
		translated = list(filter(non_empty, translated.read_text('UTF-8').split('\n')))
		match: Dict[int, Dict[int, str]] = {}
		assert len(original) == len(translated)
		assert len(original) == len(self.sentences)
		for i, sentence in enumerate(self.sentences):
			orig = original[i]
			trans = translated[i]
			if len(sentence.captions) > 1:
				new_match = sentence.match_captions_with_estimate(orig, trans)
				match[i] = new_match
			else:
				match[i] = {0: trans}

		return match

	def new_caption_set_from_match(self, match: Dict[int, Dict[int, str]]) -> CaptionSet:
		new_captions = []
		for s, sentence in enumerate(self.sentences):
			for c, caption in enumerate(sentence.captions):
				trans = match[s][c]
				new_caption = deepcopy(caption.raw_caption)
				new_caption.nodes = [CaptionNode.create_text(trans.strip())]
				new_captions.append(new_caption)

				# print(f'"{caption.raw_text}"', f'"{trans}"')
		new_caption_set = CaptionSet({'en': new_captions})
		return new_caption_set


input_file = Path("./sendung-vom-15112020-video-ut102~_type-webvtt.vtt")
read_srt = WebVTTReader().read(input_file.read_text('UTF-8'), lang='de')
sentence_manager = SentenceManager()
for raw_caption in read_srt.get_captions('de'):
	caption = MyCaption(raw_caption)
	sentence_manager.add_caption(caption)

# sentence_manager.finish()
# print(sentence_manager)

# sentence_manager.write_to_file(Path("./output.txt"))
match = sentence_manager.match_translation_from_file(Path("./output_fixed.txt"), Path("./translated.txt"))
new_caption_set = sentence_manager.new_caption_set_from_match(match)
srt_output = SRTWriter().write(new_caption_set)
print(srt_output)
Path("./translated.srt").write_text(srt_output, 'UTF-8')
