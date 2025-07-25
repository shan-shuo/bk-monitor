"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2022 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import functools
import operator
import re
import typing
from dataclasses import dataclass
from typing import Any

from apm_ebpf.apps import logger
from apm_ebpf.constants import DeepflowComp
from apm_ebpf.handlers.provisioning import ApmEbpfProvisioning
from apm_ebpf.handlers.workload import WorkloadContent, WorkloadHandler
from bk_dataview.provisioning import sync_data_sources
from bkm_space.api import SpaceApi
from bkm_space.define import SpaceTypeEnum
from bkm_space.utils import bk_biz_id_to_space_uid
from bkmonitor.utils import group_by
from bkmonitor.utils.bcs import BcsKubeClient
from bkmonitor.utils.tenant import bk_biz_id_to_bk_tenant_id
from core.drf_resource import api


@dataclass
class DeepflowDatasourceInfo:
    bk_biz_id: int = None
    name: str = None
    request_url: str = None
    # tracingUrl为可选项
    tracing_url: str = None

    @property
    def is_valid(self):
        if not self.bk_biz_id or not self.name or not self.request_url:
            return False

        return True


class DeepflowInstaller:
    # 请求超时时间
    _REQUEST_TIMEOUT = 10

    def __init__(self, cluster_id):
        self.cluster_id = cluster_id
        self.bcs_client = BcsKubeClient(self.cluster_id)

    def check_installed(self):
        """
        检查集群是否安装了ebpf
        """
        namespace = DeepflowComp.NAMESPACE

        # 获取Deployment 使用线程池获取的目的是便于处理超时 因为 K8S SDK 没有提供超时的参数 会导致任务长时间在这里卡主
        deployments = self.list_deployments(namespace)
        if deployments is None:
            return

        for deployment in deployments.items:
            content = WorkloadContent.deployment_to(deployment)
            if self._check_deployment(content):
                logger.info(f"[DeepflowInstaller] (cluster: {self.cluster_id})found valid deployment: {content.name}")
                WorkloadHandler.upsert(self.cluster_id, namespace, content)

        services = self.list_services(namespace)
        if services is None:
            return

        for service in services.items:
            content = WorkloadContent.service_to(service)
            if self._check_service(content):
                logger.info(f"[DeepflowInstaller] (cluster: {self.cluster_id})found valid service: {content.name}")
                WorkloadHandler.upsert(self.cluster_id, DeepflowComp.NAMESPACE, content)

    def list_deployments(self, namespace):
        """获取命名空间下的 deployment"""
        return self.bcs_client.client_request(self.bcs_client.api.list_namespaced_deployment, namespace=namespace)

    def list_services(self, namespace):
        """获取命名空间下的 service"""
        return self.bcs_client.client_request(self.bcs_client.core_api.list_namespaced_service, namespace=namespace)

    @classmethod
    def check_deployment(cls, content, required_deployment):
        """检查 deployment 中镜像名称是否和要求的一致"""
        image_name = cls._exact_image_name(content.image)
        return image_name == required_deployment

    @classmethod
    def _exact_image_name(cls, image):
        return image.split("/")[-1].split(":")[0]

    @classmethod
    def generator(cls):
        while True:
            yield functools.partial(cls)

    def _check_deployment(self, content):
        # 对镜像名称进行匹配
        for i in DeepflowComp.required_deployments():
            if self.check_deployment(content, i):
                return True

        return False

    @classmethod
    def check_service(cls, content, required_service):
        return re.match(required_service, content.name)

    def _check_service(self, content):
        # service名称可以为deepflow-xx的任意变形
        for i in DeepflowComp.required_services():
            if bool(self.check_service(content, i)):
                return True

        return False


class DeepflowHandler:
    _scheme = "http"

    def __init__(self, bk_biz_id):
        self.bk_biz_id = int(bk_biz_id)

    @classmethod
    def _find_deployment(cls, instances):
        res = []
        req_names = []
        for i in DeepflowComp.required_deployments():
            v = next(
                (
                    j
                    for j in instances
                    if DeepflowInstaller.check_deployment(WorkloadContent.json_to_deployment(j.content), i)
                ),
                None,
            )
            if v:
                res.append(v)
            else:
                req_names.append(i)

        return res, req_names

    @classmethod
    def _find_service(cls, instances):
        res = []
        req_names = []
        for i in DeepflowComp.required_services():
            v = next(
                (
                    j
                    for j in instances
                    if DeepflowInstaller.check_service(WorkloadContent.json_to_service(j.content), i)
                ),
                None,
            )
            if v:
                res.append(v)
            else:
                req_names.append(i)

        return res, req_names

    def list_datasources(self):
        """
        获取业务下可用的数据源
        """
        res = []
        deployments = WorkloadHandler.list_deployments(self.bk_biz_id, DeepflowComp.NAMESPACE)

        cluster_deploy_mapping = group_by(deployments, operator.attrgetter("cluster_id"))

        valid_cluster_ids = []
        # Step1: 过滤出有效的Deployment
        for cluster_id, items in cluster_deploy_mapping.items():
            sorted_items = sorted(items, key=lambda i: i.last_check_time, reverse=True)
            valid_deploys, req_names = self._find_deployment(sorted_items)
            if req_names:
                logger.warning(
                    f"[DeepflowHandler] there is no"
                    f" complete deployment in cluster: {cluster_id} of bk_biz_id: {self.bk_biz_id}"
                    f"(missing: {','.join(req_names)}). this cluster will be ignored."
                )
                continue

            invalid_item = next((i for i in valid_deploys if not i.is_normal), None)
            if invalid_item:
                logger.warning(
                    f"[DeepflowHandler] "
                    f"an abnormal deployment({invalid_item.name}) was found, this cluster will be ignored."
                )
                continue

            valid_cluster_ids.append(cluster_id)

        # Step2: 过滤出有效的Service
        for cluster_id in valid_cluster_ids:
            services = WorkloadHandler.list_services(self.bk_biz_id, DeepflowComp.NAMESPACE, cluster_id)
            sorted_items = sorted(services, key=lambda i: i.last_check_time, reverse=True)
            valid_services, req_names = self._find_service(sorted_items)
            if req_names:
                logger.warning(
                    f"[DeepflowHandler] there is no"
                    f" complete service in cluster: {cluster_id} of bk_biz_id: {self.bk_biz_id}"
                    f"(missing: {','.join(req_names)}). this cluster will be ignored."
                )
                continue

            logger.info(f"[DeepflowHandler] valid datasource of cluster_id: {cluster_id}")
            info = DeepflowDatasourceInfo(bk_biz_id=self.bk_biz_id, name=f"DeepFlow-{cluster_id}")

            for service in valid_services:
                content = WorkloadContent.json_to_service(service.content)
                if DeepflowInstaller.check_service(content, DeepflowComp.SERVICE_SERVER_REGEX):
                    # 从deepflow-server获取RequestUrl
                    info.request_url = self.get_server_access(cluster_id, service.content)
                if DeepflowInstaller.check_service(content, DeepflowComp.SERVICE_APP_REGEX):
                    # 从deepflow-app获取TracingUrl
                    info.tracing_url = self.get_app_access(cluster_id, service.content)

            if info.is_valid:
                res.append(info)

        return res

    def _get_cluster_access_ip_by_client(self, cluster_id):
        """
        获取集群某个节点的访问IP
        """
        bcs_client = BcsKubeClient(cluster_id)
        nodes = bcs_client.core_api.list_node()

        for node in nodes.items:
            if node.status.addresses:
                for addr in node.status.addresses:
                    if addr.type == "InternalIP":
                        return addr.address
        return None

    def _get_cluster_access_ip_by_api(self, cluster_id):
        try:
            bk_tenant_id = bk_biz_id_to_space_uid(self.bk_biz_id)
        except ValueError:
            return None
        nodes = api.kubernetes.fetch_k8s_node_list_by_cluster(
            {"bk_tenant_id": bk_tenant_id, "bcs_cluster_id": cluster_id}
        )
        for node in nodes:
            node_ip = node.get("node_ip")
            if node_ip and node.get("status") == "Ready":
                return node_ip
        return None

    def _get_cluster_access_ip(self, cluster_id):
        access_ip = None
        # 当使用 BCS Client 获取不到集群节点 IP 时，使用监控自身 API 进行兜底
        get_cluster_access_ip_funcs: list[typing.Callable[[str], str | None]] = [
            self._get_cluster_access_ip_by_client,
            self._get_cluster_access_ip_by_api,
        ]
        for get_cluster_access_ip_func in get_cluster_access_ip_funcs:
            try:
                access_ip = get_cluster_access_ip_func(cluster_id)
            except Exception as e:
                logger.warning(
                    "[DeepflowHandler][%s] failed to get node address: bcs_cluster_id -> %s, err -> %s",
                    get_cluster_access_ip_func.__name__,
                    cluster_id,
                    e,
                )
            if access_ip:
                logger.info(
                    "[DeepflowHandler][%s] get node address -> %s, bcs_cluster_id -> %s",
                    get_cluster_access_ip_func.__name__,
                    access_ip,
                    cluster_id,
                )
                return access_ip
        return access_ip

    @property
    def _clusters(self):
        """
        获取业务下所有集群列表
        """
        if not self.bk_biz_id:
            logger.warning("unable to get cluster list because bk_biz_id is empty")
            return []

        space_info = SpaceApi.get_space_detail(bk_biz_id=self.bk_biz_id)
        space_type = space_info.space_type_id

        params: dict[str, Any]
        if space_type == SpaceTypeEnum.BKCC.value:
            params = {"businessID": self.bk_biz_id}
        elif space_type == SpaceTypeEnum.BCS.value:
            params = {"projectID": space_info.space_id}
        elif space_type == SpaceTypeEnum.BKCI.value and space_info.space_code:
            params = {"projectID": space_info.space_code}
        else:
            logger.warning(f"can not obtained cluster info from bk_biz_id: {self.bk_biz_id}(type: {space_type})")
            return []
        try:
            params["bk_tenant_id"] = bk_biz_id_to_bk_tenant_id(self.bk_biz_id)
        except ValueError:
            return []
        clusters = api.bcs_cluster_manager.fetch_clusters(**params)
        logger.info(f"{len(clusters)} clusters with bk_biz_id: {self.bk_biz_id} are obtained")

        # 过滤共享集群
        return [i for i in clusters if not i["is_shared"]]

    @property
    def server_addresses(self):
        """
        获取业务下所有已发现集群的service: deepflow-server的访问地址
        """
        res = {}
        for cluster_id in WorkloadHandler.list_deepflow_cluster_ids(self.bk_biz_id):
            u = self.get_server_access(cluster_id)
            if u:
                res[cluster_id] = u

        return res

    @property
    def app_addresses(self):
        """
        获取业务下所有已发现集群的service: deepflow-app访问地址
        """
        res = {}
        for cluster_id in WorkloadHandler.list_deepflow_cluster_ids(self.bk_biz_id):
            u = self.get_app_access(cluster_id)
            if u:
                res[cluster_id] = u

        return res

    def get_server_access(self, cluster_id, service_content=None):
        """
        获取DeepFlow-server访问地址
        """
        if not service_content:
            server_service = self._get_service_instance(cluster_id, DeepflowComp.SERVICE_SERVER_REGEX)
            if not server_service:
                return None
            service_content = server_service.content
        return self._get_access(
            cluster_id,
            service_content,
            DeepflowComp.SERVICE_SERVER_PORT_QUERY,
        )

    def get_app_access(self, cluster_id, service_content=None):
        """
        获取DeepFlow-app访问地址
        """
        if not service_content:
            app_service = self._get_service_instance(cluster_id, DeepflowComp.SERVICE_APP_REGEX)
            if not app_service:
                return None
            service_content = app_service.content

        return self._get_access(
            cluster_id,
            service_content,
            DeepflowComp.SERVICE_APP_PORT_QUERY,
        )

    def _get_service_instance(self, cluster_id, specific_service):
        services = WorkloadHandler.list_services(self.bk_biz_id, DeepflowComp.NAMESPACE, cluster_id)

        return next(
            (
                i
                for i in services
                if DeepflowInstaller.check_service(WorkloadContent.json_to_service(i.content), specific_service)
            ),
            None,
        )

    def _get_access(self, cluster_id, service_content, port_name):
        node_ip = self._get_cluster_access_ip(cluster_id)
        if not node_ip:
            return None

        port = WorkloadContent.extra_port(service_content, port_name)
        url = f"{self._scheme}://{node_ip}:{port}"

        return url

    @classmethod
    def install_grafana(cls):
        """注册grafana仪表盘"""

        check_biz_ids = WorkloadHandler.list_exist_biz_ids()
        logger.info(
            f"[GrafanaInstaller] start check "
            f"if dashboards are installed in {len(check_biz_ids)} businesses({check_biz_ids})"
        )

        for biz_id in check_biz_ids:
            try:
                logger.info(f"[GrafanaInstaller] biz_id: {biz_id} start check")
                # 注册数据源
                org_info = api.grafana.get_organization_by_name(name=biz_id).get("data", {})
                if not org_info:
                    logger.warning(f"[GrafanaInstaller] org_name: {biz_id} return null")
                    continue
                logger.info(f"[GrafanaInstaller] biz_id: {biz_id} obtain org_info: {org_info}")
                org_id = org_info.get("id")
                if not org_id:
                    logger.warning(f"[GrafanaInstaller] can not found org_name: {biz_id} in grafana?")
                    continue
                logger.info(f"[GrafanaInstaller] biz_id: {biz_id} obtain org_id: {org_id}")
                datasources = cls(biz_id).list_datasources()
                if not datasources:
                    logger.info(f"[GrafanaInstaller] biz_id: {biz_id} has not valid datasource, skip")
                    continue
                logger.info(f"[GrafanaInstaller] biz_id: {biz_id} found {len(datasources)} datasource, registry")
                sync_data_sources(
                    org_id,
                    ApmEbpfProvisioning.convert_to_datasource(
                        list(datasources), DeepflowComp.GRAFANA_DATASOURCE_TYPE_NAME
                    ),
                )
                logger.info(f"[GrafanaInstaller] biz_id: {biz_id} datasource registry finished")

                # 注册仪表盘
                mapping = ApmEbpfProvisioning.get_dashboard_mapping(biz_id)
                ApmEbpfProvisioning.upsert_dashboards(org_id, biz_id, mapping)
                logger.info(f"[GrafanaInstaller] biz_id: {biz_id} dashboard registry finished")
            except Exception as e:
                logger.exception(f"[GrafanaInstaller] biz_id: {biz_id} occur exception: {e}")
