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
  <div class="empty-container">
    <template v-if="isFirstSearch">
      <bk-exception
        class="exception-wrap-item exception-part"
        scene="part"
        type="empty"
      >
        <div class="empty-card">
          <div class="empty-message">{{ $t('暂未进行检索') }}</div>
          <div class="empty-main">
            <div class="suggest-title">{{ $t('您可以按照以下方式进行检索') }}</div>
            <div class="suggest-list">
              <span>
                1.
                <i18n path="当前是否有数据源，如果没有请 {0}">
                  <span
                    class="blue-btn"
                    @click="handleBtnClick('goToConfig')"
                    >{{ $t('前往配置') }}</span
                  >
                </i18n>
              </span>
              <span> 2. {{ $t('检查查询条件是否完整，是否有报错') }}</span>
              <span>
                3.
                <i18n path="当前可能是手动查询，请 {0}">
                  <span
                    class="blue-btn"
                    @click="handleBtnClick('clickToQuery')"
                    >{{ $t('点击查询') }}</span
                  >
                </i18n>
              </span>
            </div>
          </div>
        </div>
      </bk-exception>
    </template>
    <template v-else>
      <bk-exception
        class="exception-wrap-item exception-part"
        scene="part"
        type="search-empty"
      >
        <div class="empty-card">
          <div class="empty-message">{{ $t('查询无数据') }}</div>
          <div class="empty-main">
            <div class="suggest-title">{{ $t('您可以按照以下方式优化检索结果') }}</div>
            <div class="suggest-list">
              <span>
                1.
                <i18n path="检查 {0} 情况">
                  <span
                    class="blue-btn"
                    @click="handleBtnClick('indexConfig')"
                    >{{ $t('数据源配置') }}</span
                  >
                </i18n>
              </span>
              <span>2. {{ $t('检查右上角的索时间范围') }}</span>
              <span>3. {{ $t('优化查询语句') }}</span>
              <div class="grammar-list">
                <span
                  v-for="(item, index) in grammarMap"
                  :key="index"
                >
                  <span>{{ item.key }}</span> : <span>{{ item.value }}</span>
                </span>
              </div>
            </div>
          </div>
          <div
            class="more-rule"
            @click="handleBtnClick('queryString')"
          >
            {{ $t('查看更多语法规则') }}
            <span class="bklog-icon bklog-tiaozhuan"></span>
          </div>
        </div>
      </bk-exception>
    </template>
  </div>
</template>

<script>
  import docsMixin from '@/mixins/docs-link-mixin';
  import { mapGetters, mapState } from 'vuex';
  export default {
    mixins: [docsMixin],
    inheritAttrs: false,
    data() {
      return {
        grammarMap: [
          {
            key: this.$t('带字段全文检索更高效'),
            value: 'log:abc',
          },
          {
            key: this.$t('模糊检索使用通配符'),
            value: this.$t('abc* 或 ab?c'),
          },
          {
            key: this.$t('双引号匹配完整字符串'),
            value: 'log:"ERROR MSG"',
          },
          {
            key: this.$t('数值字段范围匹配'),
            value: 'count:[1 TO 5]',
          },
          {
            key: this.$t('正则匹配'),
            value: 'name:/joh?n(ath[oa]n)/',
          },
          {
            key: this.$t('组合检索注意大写'),
            value: 'log: (error OR info)',
          },
        ],
        routeNameList: {
          // 路由跳转name
          log: 'manage-collection',
          custom: 'custom-report-detail',
          manage: 'bkdata-index-set-manage',
          indexManage: 'log-index-set-manage',
        },
        detailJumpRouteKey: 'log',
      };
    },

    computed: {
      ...mapGetters({
        indexId: 'indexId',
        spaceUid: 'spaceUid',
      }),
      ...mapState({
        indexSetItem: 'indexFieldInfo',
        indexSetQueryResult: 'indexSetQueryResult',
      }),
      indexParams() {
        const { scenario_id, collector_scenario_id, index_set_id } = this.indexSetItem;
        return this.indexSetItem ? { scenario_id, collector_scenario_id, index_set_id } : {};
      },
      retrieveSearchNumber() {
        return this.indexSetQueryResult.search_count;
      },
      isFirstSearch() {
        return this.retrieveSearchNumber < 1;
      },
    },
    watch: {
      indexParams: {
        handler(nVal) {
          if (JSON.stringify(nVal) === '{}') return;
          if (nVal.scenario_id === 'log') {
            // 索引集类型为采集项或自定义上报
            if (nVal.collector_scenario_id === null) {
              // 若无日志类型 则类型为索引集
              this.getDetailJumpRouteKey('setIndex');
              return;
            }
            // 判断是否是自定义上报类型
            this.getDetailJumpRouteKey(nVal.collector_scenario_id === 'custom' ? 'custom' : 'log');
            return;
          }
          // 当scenario_id不为log（采集项，索引集，自定义上报）时
          this.getDetailJumpRouteKey(nVal.scenario_id);
        },
        immediate: true,
      },
    },
    mounted() {
      const el = document.querySelector('.bk-table-empty-block');
      if (el) el.classList.add('empty-clear-width');
    },
    methods: {
      handleBtnClick(clickType) {
        let baseUrl = window.__IS_MONITOR_COMPONENT__ ? window.site_url : window.SITE_URL;
        if (!baseUrl.startsWith('/')) baseUrl = `/${baseUrl}`;
        if (!baseUrl.endsWith('/')) baseUrl += '/';
        baseUrl = `${window.__IS_MONITOR_COMPONENT__ ? window.bk_log_search_url : window.location.origin}` + baseUrl;
        switch (clickType) {
          case 'queryString': // 查询更多语法
            this.handleGotoLink('queryString');
            break;
          case 'indexConfig':
            {
              // 索引配置
              if (JSON.stringify(this.indexParams) === '{}') {
                this.$bkMessage({
                  theme: 'error',
                  message: this.$t('未找到对应的采集项'),
                });
                return;
              }
              const params = {};
              if (['manage', 'indexManage'].includes(this.detailJumpRouteKey)) {
                params.indexSetId = this.indexParams?.index_set_id;
              } else {
                params.collectorId = this.indexParams?.collector_config_id;
              }
              const { href } = this.$router.resolve({
                name: this.routeNameList[this.detailJumpRouteKey],
                params,
                query: {
                  spaceUid: this.$store.state.spaceUid,
                },
              });
              window.open(href, '_blank');
            }
            break;
          case 'goToConfig':
            {
              // 前往配置
              const jumpUrl = `${baseUrl}#/manage/log-collection/collection-item?spaceUid=${this.spaceUid}`;
              window.open(jumpUrl, '_blank');
            }
            break;
          case 'clickToQuery': // 点击查询
            this.$emit('should-retrieve');
            break;
        }
      },
      getDetailJumpRouteKey(detailStr) {
        if (['es', 'bkdata'].includes(detailStr)) {
          this.detailJumpRouteKey = 'manage';
        } else if (detailStr === 'setIndex') {
          this.detailJumpRouteKey = 'indexManage';
        } else {
          this.detailJumpRouteKey = detailStr;
        }
      },
    },
  };
</script>

<style lang="scss" scoped>
  .empty-container {
    margin: 20px 0;

    .empty-card {
      margin-top: 24px;
      color: #63656e;

      .empty-main {
        min-width: 230px;
        font-size: 12px;
        text-align: left;

        .suggest-title {
          padding: 8px 0;
          color: #979ba5;
        }

        .suggest-list {
          display: flex;
          flex-direction: column;
          line-height: 18px;

          .grammar-list {
            display: flex;
            flex-direction: column;
            margin-left: 14px;
          }
        }
      }

      .more-rule {
        margin-top: 8px;
        font-size: 12px;
        color: #3a84ff;
        cursor: pointer;

        .bklog-icon {
          display: inline-block;
          transform: scale(0.8) translate3d(-2px, -1px, 0);
        }
      }
    }

    .blue-btn {
      color: #3a84ff;
      cursor: pointer;
    }

    :deep(.exception-image) {
      height: 180px;
    }
  }
</style>

<style lang="scss">
  .empty-clear-width {
    /* stylelint-disable-next-line declaration-no-important */
    width: auto !important;
  }
</style>
