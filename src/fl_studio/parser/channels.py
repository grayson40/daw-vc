import pyflp
from typing import Dict, Any


class FLChannelParser:
    def __init__(self, project: pyflp.Project):
        self.project = project
        self.channels = project.channels

    def get_state(self) -> Dict[str, Any]:
        return {
            'rack_settings': self._parse_rack_settings(),
            'groups': [self._parse_group(g) for g in self.channels.groups],
            'channels': self._parse_channels()
        }

    def _parse_rack_settings(self) -> Dict[str, Any]:
        return {
            'height': self.channels.height,
            'fit_to_steps': self.channels.fit_to_steps,
            'swing': self.channels.swing
        }

    def _parse_group(self, group) -> Dict[str, Any]:
        return {
            'name': group.name,
        }

    def _parse_channels(self) -> Dict[str, Any]:
        return {
            'samplers': [self._parse_sampler(ch) for ch in self.channels.samplers],
            'instruments': [self._parse_instrument(ch) for ch in self.channels.instruments],
            'layers': [self._parse_layer(ch) for ch in self.channels.layers],
            'automations': [self._parse_automation(ch) for ch in self.channels.automations]
        }

    def _parse_base_channel(self, channel) -> Dict[str, Any]:
        return {
            'name': channel.name,
            'display_name': channel.display_name,
            'internal_name': channel.internal_name,
            'enabled': channel.enabled,
            'locked': channel.locked,
            'volume': channel.volume,
            'pan': channel.pan,
            'color': channel.color,
            'icon': channel.icon,
            'zipped': channel.zipped
        }

    def _parse_sampler(self, sampler) -> Dict[str, Any]:
        return {
            'base': self._parse_base_channel(sampler),
            'sample_path': str(sampler.sample_path) if sampler.sample_path else None,
            'content': self._parse_content(sampler.content),
            'fx': self._parse_fx(sampler.fx),
            'envelopes': self._parse_envelopes(sampler.envelopes),
            'filter': self._parse_filter(sampler.filter),
            'playback': self._parse_playback(sampler.playback),
            'stretching': self._parse_stretching(sampler.stretching),
            'lfos': self._parse_lfos(sampler.lfos),
            'tracking': self._parse_tracking(sampler.tracking)
        }

    def _parse_instrument(self, instrument) -> Dict[str, Any]:
        return {
            'base': self._parse_base_channel(instrument),
            'plugin': instrument.plugin,  # TODO: Figure out how to get more plugin info
            'pitch_shift': instrument.pitch_shift,
            'insert': instrument.insert,
            'tracking': self._parse_tracking(instrument.tracking)
        }

    def _parse_layer(self, layer) -> Dict[str, Any]:
        return {
            'base': self._parse_base_channel(layer),
            'crossfade': layer.crossfade,
            'random': layer.random
        }

    def _parse_automation(self, automation) -> Dict[str, Any]:
        return {
            'base': self._parse_base_channel(automation),
            'lfo': automation.lfo.amount if automation.lfo else None
        }

    def _parse_content(self, content) -> Dict[str, Any]:
        if not content:
            return {}
        return {
            'declick_mode': content.declick_mode,
            'keep_on_disk': content.keep_on_disk,
            'resample': content.resample,
            'load_regions': content.load_regions,
            'load_slices': content.load_slices
        }

    def _parse_fx(self, fx) -> Dict[str, Any]:
        if not fx:
            return {}
        return {
            'reverb': self._parse_reverb(fx.reverb),
            'boost': fx.boost,
            'clip': fx.clip,
            'crossfade': fx.crossfade,
            'cutoff': fx.cutoff,
            'fade_in': fx.fade_in,
            'fade_out': fx.fade_out,
            'fade_stereo': fx.fade_stereo,
            'fix_trim': fx.fix_trim,
            'freq_tilt': fx.freq_tilt,
            'resonance': fx.resonance,
            'stereo_delay': fx.stereo_delay,
            'reverse': fx.reverse,
            'inverted': fx.inverted,
            'normalize': fx.normalize,
            'ringmod': fx.ringmod,
            'pogo': fx.pogo,
            'start': fx.start,
            'stereo_delay': fx.stereo_delay,
            'trim': fx.trim
        }

    def _parse_reverb(self, reverb) -> Dict[str, Any]:
        if not reverb:
            return {}
        return {
            'mix': reverb.mix,
            'type': reverb.type
        }

    def _parse_filter(self, filter) -> Dict[str, Any]:
        if not filter:
            return {}
        return {
            'type': filter.type,
            'mod_x': filter.mod_x,
            'mod_y': filter.mod_y
        }

    def _parse_playback(self, playback) -> Dict[str, Any]:
        if not playback:
            return {}
        return {
            'ping_pong_loop': playback.ping_pong_loop,
            'start_offset': playback.start_offset,
            'use_loop_points': playback.use_loop_points
        }

    def _parse_stretching(self, stretching) -> Dict[str, Any]:
        if not stretching:
            return {}
        return {
            'mode': stretching.mode,
            'multiplier': stretching.multiplier,
            'pitch': stretching.pitch,
            'time': stretching.time
        }

    def _parse_tracking(self, tracking) -> Dict[str, Any]:
        if not tracking:
            return {}
        return {
            k: {
                'middle_value': v.middle_value,
                'mod_x': v.mod_x,
                'mod_y': v.mod_y,
                'pan': v.pan
            } for k, v in tracking.items()
        }

    def _parse_envelopes(self, envelopes) -> Dict[str, Dict[str, Any]]:
        if not envelopes:
            return {}
        return {
            target: {
                'amount': env.amount,
                'attack': env.attack,
                'decay': env.decay,
                'sustain': env.sustain,
                'release': env.release,
                'attack_tension': env.attack_tension,
                'decay_tension': env.decay_tension,
                'release_tension': env.release_tension,
                'enabled': env.enabled,
                'synced': env.synced,
                'hold': env.hold,
                'predelay': env.predelay,
            } for target, env in envelopes.items()
        }

    def _parse_lfos(self, lfos) -> Dict[str, Dict[str, Any]]:
        if not lfos:
            return {}
        return {
            target: {
                'amount': lfo.amount,
                'attack': lfo.attack,
                'predelay': lfo.predelay,
                'retrig': lfo.retrig,
                'shape': lfo.shape,
                'speed': lfo.speed,
                'synced': lfo.synced,
            } for target, lfo in lfos.items()
        }
