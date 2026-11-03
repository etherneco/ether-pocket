"""Replay PDR discovery when the notifier module loads after discovery."""
from pathlib import Path

source = next(Path('/opt/etherpocket/audio-source').glob('*/techpack/audio/dsp/audio_pdr.c'))
text = source.read_text()
old = '\treturn srcu_notifier_chain_register(&audio_pdr_cb_list, nb);'
new = '''\tint ret;
\tret = srcu_notifier_chain_register(&audio_pdr_cb_list, nb);
\t/* Discovery can finish before dependent modules register. */
\tif (!ret && audio_pdr_services[AUDIO_PDR_DOMAIN_ADSP].total_domains == 1)
\t\tnb->notifier_call(nb, AUDIO_PDR_FRAMEWORK_UP, NULL);
\treturn ret;'''
if old in text:
    source.write_text(text.replace(old, new))
elif new not in text:
    raise RuntimeError('Unexpected audio PDR source')
