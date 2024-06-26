<!--
* Tencent is pleased to support the open source community by making
* 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
*
* Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
*
* 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
*
* License for 蓝鲸智云PaaS平台 (BlueKing PaaS):
*
* ---------------------------------------------------
* Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
* documentation files (the "Software"), to deal in the Software without restriction, including without limitation
* the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
* to permit persons to whom the Software is furnished to do so, subject to the following conditions:
*
* The above copyright notice and this permission notice shall be included in all copies or substantial portions of
* the Software.
*
* THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
* THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
* AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
* CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
* IN THE SOFTWARE.
-->

<template>
  <div class="yaml-container">
    <monaco-editor
      v-model="editorValue"
      :language="language"
      :warning-list="warningList"
      @get-problem-state="getProblemState"
    >
      <template #right>
        <div class="load">
          <span
            class="load-tips"
            v-bk-tooltips="{ distance: 20, content: $t('上传'), delay: 300 }"
          >
            <span
              class="bk-icon icon-upload-cloud"
              @click="updateYAMLDocument"
            ></span>
          </span>
          <span
            class="load-tips"
            v-bk-tooltips="{ distance: 20, content: $t('下载'), delay: 300 }"
          >
            <span
              class="bk-icon icon-download"
              @click="downloadYAMLDocument()"
            ></span>
          </span>
        </div>
      </template>
    </monaco-editor>
  </div>
</template>
<script>
  import { base64Encode, base64Decode } from '@/common/util';
  import { setDiagnosticsOptions } from 'monaco-yaml';

  import monacoEditor from './monaco-editor';

  export default {
    components: {
      monacoEditor,
    },
    model: {
      prop: 'value',
      event: 'change',
    },
    props: {
      value: {
        type: String,
        default: '',
      },
      valueType: {
        type: String,
        default: 'default',
        validator: value => ['default', 'base64'].includes(value),
      },
      yamlFormData: {
        type: Object,
        default: () => ({}),
      },
      clusterId: {
        type: String,
        default: '',
      },
    },
    data() {
      return {
        language: 'yaml',
        editorValue: '',
        warningList: [], // 警告列表
        editor: null,
        inputDocument: null,
        timer: null,
        isHaveErrorProblem: false,
      };
    },
    computed: {
      isHaveCannotSubmitWaring() {
        return this.warningList.some(item => item.startLineNumber === 0 && item.endLineNumber === 0);
      },
      getSubmitState() {
        return !(this.isHaveErrorProblem || this.isHaveCannotSubmitWaring);
      },
    },
    watch: {
      editorValue(val) {
        const base64Str = base64Encode(val);
        this.$emit('change', this.valueType === 'default' ? val : base64Str);
        clearTimeout(this.timer);
        this.timer = setTimeout(() => {
          this.checkWarning(base64Str);
        }, 1000);
      },
    },
    mounted() {
      this.initInputType();
      setDiagnosticsOptions({
        validate: true,
        enableSchemaRequest: true,
        format: true,
        hover: true,
        completion: true,
      });
    },
    beforeUnmount() {
      this.inputDocument.removeEventListener('change', this.inputFileEvent);
      this.inputDocument = null;
    },
    methods: {
      downloadYAMLDocument(filename = '') {
        const eleLink = document.createElement('a');

        const today = new Date();
        // 日期
        const DD = String(today.getDate()).padStart(2, '0'); // 获取日
        const MM = String(today.getMonth() + 1).padStart(2, '0'); // 获取月份，1 月为 0
        const yyyy = today.getFullYear(); // 获取年
        // 时间
        const hh = String(today.getHours()).padStart(2, '0'); // 获取当前小时数(0-23)
        const mm = String(today.getMinutes()).padStart(2, '0'); // 获取当前分钟数(0-59)
        const ss = String(today.getSeconds()).padStart(2, '0'); // 获取当前秒数(0-59)
        const time = `${yyyy}${MM}${DD}${hh}${mm}${ss}`;
        eleLink.download = filename || `bk_log_search_download_${time}.yaml`;
        eleLink.style.display = 'none';
        // 字符内容转变成blob地址
        const blob = new Blob([this.editorValue]);
        eleLink.href = URL.createObjectURL(blob);
        // 触发点击
        document.body.appendChild(eleLink);
        eleLink.click();
        document.body.removeChild(eleLink);
      },
      updateYAMLDocument() {
        this.inputDocument.click(); // 本地文件回填
      },
      /**
       * @desc: 初始化上传yaml文件操作dom
       */
      initInputType() {
        const inputDocument = document.createElement('input');
        inputDocument.type = 'file';
        inputDocument.style.display = 'none';
        inputDocument.addEventListener('change', this.inputFileEvent);
        this.inputDocument = inputDocument;
        this.editorValue = base64Decode(this.value);
      },
      inputFileEvent() {
        // 检查文件是否选择:
        if (!this.inputDocument.value) return;
        const file = this.inputDocument.files[0];
        if (!/.*(?<=\.yaml|\.yml)$/.test(file.name)) {
          this.$bkMessage({
            theme: 'error',
            message: this.$t('不是有效的yaml文件'),
          });
          return;
        }
        // 读取文件:
        const reader = new FileReader();
        reader.onload = e => {
          const data = e.target.result;
          this.editorValue = data;
        };
        // 以Text的形式读取文件:
        reader.readAsText(file);
      },
      checkWarning(yaml) {
        if (yaml === '' || this.isHaveErrorProblem) {
          this.warningList = [];
          return;
        }
        this.$http
          .request('container/yamlJudgement', {
            data: {
              bk_biz_id: this.$store.state.bkBizId,
              bcs_cluster_id: this.clusterId,
              yaml_config: yaml,
            },
          })
          .then(res => {
            if (res.code === 0) {
              const { parse_result: parseResult, parse_status: parseStatus } = res.data;
              if (Array.isArray(parseResult) && !parseStatus) {
                this.warningList = parseResult.map(item => ({
                  startLineNumber: item.start_line_number,
                  endLineNumber: item.end_line_number,
                  message: item.message,
                }));
                return;
              }

              if (parseStatus) {
                this.warningList = [];
                const yamlFormData = parseResult;
                yamlFormData.configs.forEach(item => {
                  delete item.raw_config;
                });
                this.$emit('update:yaml-form-data', yamlFormData);
              }
            }
          })
          .catch(err => {
            console.warn(err);
          });
      },
      getProblemState(state) {
        this.isHaveErrorProblem = state;
      },
    },
  };
</script>
<style lang="scss" scoped>
  .yaml-container {
    width: 74%;
    min-width: 800px;
    margin: 20px 0 0 115px;
  }

  .load {
    display: flex;
    align-items: center;
  }

  .icon-upload-cloud {
    font-size: 20px;
  }

  :deep(.bk-icon) {
    margin-right: 0px;
  }

  .load-tips {
    margin-right: 20px;
  }

  .icon-download {
    display: inline-block;
    transform: translateY(-2px);
  }
</style>
