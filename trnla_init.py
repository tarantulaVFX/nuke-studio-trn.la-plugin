# --------------------------Trn.la Plugin For Nuke Studio--------------------------------
# Register Trnla Custom Processors and Tasks
#
# Author: Moses Molina
# email:  moses.tarantula@gmail.com
# --------------------------------------------------------------------------------------

import hiero.core
from trnla import (TrnlaShotProcessor, TrnlaShotProcessorUI, TrnlaShotProcessorPreset,
                   TrnlaTranscodeExporter, TrnlaTranscodeExporterUI, TrnlaTranscodePreset,
                   TrnlaPreviewTranscoder, TrnlaPreviewTranscoderUI, TrnlaPreviewTranscoderPreset)


hiero.core.taskRegistry.registerProcessor(TrnlaShotProcessorPreset, TrnlaShotProcessor)
hiero.ui.taskUIRegistry.registerProcessorUI(TrnlaShotProcessorPreset, TrnlaShotProcessorUI)

hiero.core.taskRegistry.registerTask(TrnlaTranscodePreset, TrnlaTranscodeExporter)
hiero.ui.taskUIRegistry.registerTaskUI(TrnlaTranscodePreset, TrnlaTranscodeExporterUI)

hiero.core.taskRegistry.registerTask(TrnlaPreviewTranscoderPreset, TrnlaPreviewTranscoder)
hiero.ui.taskUIRegistry.registerTaskUI(TrnlaPreviewTranscoderPreset, TrnlaPreviewTranscoderUI)