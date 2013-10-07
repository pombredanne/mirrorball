#
# Copyright (c) SAS Institute, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#


"""
UpdateBot is a module for the automated creation and updating of a conary
packages from a yum or apt repository.
"""

from updatebot.bot import Bot
from updatebot.current import Bot as CurrentBot
from updatebot.native import Bot as NativeBot
from updatebot.config import UpdateBotConfig
