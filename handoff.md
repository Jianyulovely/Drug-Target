# DTI 项目交接文档

更新时间：2026-09-04

## 1. 项目目标

本项目研究：在二分类药物—靶点相互作用（DTI）预测中，将只使用训练折信息构建的、无标签泄漏的相似邻居特征 S1/S2 加入 ArnoldiGCL 结构模型后，是否能在随机划分和冷启动划分下带来稳定的排序性能提升。

当前工作名：`ArnoldiGCL-S1/S2`。

需要坚持的表述边界：

- 这是计算 DTI 预测/候选优先级排序结果，不是实验验证的真实结合结果。
- 结果是 split-dependent 的，不能写成“所有数据集上都优于基线”或“普遍 SOTA”。
- DrugBAN 是匹配划分的比较方法，不要声称复现了 DrugBAN 论文中的原始数值。
- Threshold GCN 是本项目定义的阈值 GCN 比较方法，不要称为完整的外部 ColdDTI 复现。
- 15 个 seed–fold 是固定评估单元，不应表述为 15 个生物学重复。

## 2. 已完成内容

截至 2026-09-04，技术结果和结果衍生材料已经完成并通过审计：

| 项目 | 状态 |
|---|---|
| 正式 DrugBAN | 180/180；100 epochs；`input_cache=true`；`tf32=true` |
| 全部正式结果 | 1,800/1,800 = 10 个方法 × 3 个数据集 × 4 个场景 × 15 个固定 seed–fold |
| 冻结划分审计 | 通过，输出 `SPLIT_INTEGRITY_COMPLETE` |
| 完整覆盖审计 | 通过，输出 `COVERAGE_COMPLETE` |
| 结果与产物审计 | 通过，输出 `FINAL_AUDIT_COMPLETE`；`audit_results=1800`，`errors=0` |
| 运行环境清单审计 | 已生成并通过 runtime-manifest 检查 |
| 聚合结果 | `tables/`、`source_data/` 已生成 |
| 论文图 | Figure 1、Figure 2、Figure 3 已生成；支持 SVG/PDF/PNG/TIFF |
| 数据衍生文字 | Abstract、Results、Discussion、Conclusion、protocol 片段已生成 |
| LaTeX 技术报告 | 已编译为 10 页并完成页面渲染检查；未发现引用、交叉引用或版面错误 |
| 回归测试 | 队列调度、缓存等价性、S1/S2 泄漏控制、消融 shuffle 控制、后处理链、占位符门禁和 ZIP 导出测试已通过 |

## 3. 当前结果应如何解释

最终结果支持以下谨慎结论：

- ArnoldiGCL-S1/S2 在预先规定的 12 个数据集—场景条件中，有 7/12 个条件取得最高平均 AUPR。
- 相比 ArnoldiGCL structural-only，完整 S1/S2 模型在 11/12 个条件中的平均 AUPR 更高，正向差异约为 0.013–0.396。
- 其中 11 个配对比较的 BH 校正后描述性检验达到 `p<0.05`。
- 未取得最高平均 AUPR 的条件包括：BioSNAP/cold-protein、Human/cold-protein、Human/cold-pair、BindingDB/cold-protein、BindingDB/cold-pair。

因此论文应强调“无泄漏相似邻居信息在部分划分条件下有帮助，但优势依赖数据集和划分方式”，同时把非获胜条件保留在正文、表格和图中。

## 4. 尚未完成的工作

这些是投稿前剩余事项，不是实验队列事项：

### 4.1 作者和投稿信息

填写并另存为 `manuscript/SUBMISSION_METADATA.md`：

- 目标期刊和文章类型；
- 最终标题确认；
- 作者顺序、单位、ORCID、共同一作和通讯作者；
- CRediT 作者贡献；
- 利益冲突、基金、致谢；
- 伦理/知情同意说明（如期刊要求）；
- 代码仓库 URL、release tag/commit、软件许可证；
- 结果/划分归档地址或 DOI；
- 全体作者是否批准投稿版本。

模板：

- `manuscript/SUBMISSION_METADATA.template.md`
- `manuscript/SUBMISSION_METADATA.zh-CN.md`
- 详细说明：`AUTHOR_INPUT_REQUIRED.md`

### 4.2 数据许可和再分发边界

需要作者确认 BioSNAP、Human、BindingDB 原始数据的当前提供方条款。软件仓库的 MIT/BSD/Apache 许可证不等于原始数据可以自由再分发。

如果无法确认原始 CSV 的再分发权：

- 不要把原始 CSV 直接打包公开；
- 发布冻结划分索引、SHA256 校验和、处理代码、结果 JSON、聚合表和作图源数据；
- 在 README 和 Data Availability 中指向原始数据提供方。

### 4.3 目标期刊适配

当前稿件是通用 LaTeX 版本。确定期刊后，还需按目标期刊要求检查：

- 标题页、摘要和字数限制；
- 图尺寸、字体、文件格式和图注格式；
- 参考文献样式；
- 数据可用性、代码可用性和声明部分；
- 补充材料命名和上传要求。

### 4.4 最终投稿包

完成元数据和数据许可确认后：

1. 重新运行最终化脚本，使文字、表格、图和 source data 来自同一份已审计结果。
2. 重新编译最终 PDF。
3. 渲染并检查全部页面、图表、表格、参考文献和分页。
4. 生成一个新的、不覆盖旧文件的 Overleaf ZIP。
5. 记录最终代码 commit、结果归档 DOI、环境清单和数据来源版本。

## 5. 重要文件导航

### 核心脚本

- `paper_benchmark.py`：冻结划分并运行 B1–B4/M8。
- `run_drugban_fold.py`：在同一冻结划分上运行 DrugBAN。
- `run_drugban_queue.sh`：DrugBAN 队列调度器。
- `verify_split_integrity.py`：冻结划分、冷启动隔离、标签和 split signature 审计。
- `verify_paper_coverage.py`：按方法、数据集、场景和 fold 检查覆盖。
- `final_paper_audit.py`：结果身份、指标、split signature、DrugBAN 元数据和最终产物审计。
- `generate_manuscript_results.py`：从已审计 JSON 生成论文数字和文字片段。
- `plot_paper_results.py`：论文原有 Figure 2/3 的生成脚本。
- `plot_scientific_figures.py`：独立科研绘图版 Figure 2/3，输出到 `manuscript/figures/scientific/`，不覆盖论文原图。
- `postprocess_after_drugban.sh`：队列结束后的审计和后处理链。
- `finalize_overleaf_package.sh`：远程审计、同步材料、编译 PDF 和生成 Overleaf ZIP。

### 当前交付材料

- `manuscript/generated/`：五个数据衍生 LaTeX 片段。
- `manuscript/tables/`：汇总表、fold 表和覆盖表。
- `manuscript/source_data/`：fold 指标、汇总指标、配对统计、数据集清单和环境清单。
- `manuscript/figures/`：当前论文集成的 Figure 1/2/3。
- `manuscript/figures/scientific/`：最新独立科研绘图版 Figure 2/3。
- `manuscript/build_report_20260904T1150/main.pdf`：已完成页面检查的 10 页技术报告。
- `REPORT_READY_SUMMARY.md`：当前技术结果摘要。
- `DELIVERY_CHECKLIST.md`：逐项交付门禁。
- `MANUSCRIPT_CLAIM_AUDIT.md`：论文主张和证据边界审计。
- `MANUSCRIPT_REVIEW_READINESS.md`：投稿前审查风险清单。

## 6. 推荐接手顺序

### 第一步：先确认现状，不要重跑实验

先阅读本文件、`REPORT_READY_SUMMARY.md`、`DELIVERY_CHECKLIST.md` 和 `AUTHOR_INPUT_REQUIRED.md`。实验已经完成，除非审计发现明确错误，否则不要重启 DrugBAN 或旧的 `run_paper_queue.sh`。

### 第二步：完成作者元数据

复制并填写 `manuscript/SUBMISSION_METADATA.template.md`，文件名保存为 `manuscript/SUBMISSION_METADATA.md`。任何不确定的信息留给作者确认，不要由脚本猜测。

### 第三步：完成数据与代码发布决定

确认三份原始数据的提供方条款、公开仓库、代码 commit、归档 DOI、许可证和可再分发范围。若只能发布索引和校验和，要同步更新 README 和 Data Availability。

### 第四步：运行最终审计

在正式 benchmark 根目录执行：

```bash
PYTHON=/mnt/sda/fulaiyi/aspect_env/bin/python
ROOT=/mnt/sda/fulaiyi/dti_paper_20260826_v2

"$PYTHON" "$ROOT/verify_split_integrity.py" --root "$ROOT"
"$PYTHON" "$ROOT/final_paper_audit.py" --root "$ROOT" --require-artifacts --require-runtime-manifest
```

必须看到：

```text
SPLIT_INTEGRITY_COMPLETE
FINAL_AUDIT_COMPLETE
```

如果任一命令失败，不要继续生成投稿包；先处理审计错误并保留日志。

### 第五步：生成最终 Overleaf 包

在本地项目根目录使用已配置好的、经批准的 SSH 认证方式运行：

```bash
./finalize_overleaf_package.sh --overleaf-zip /path/to/a-new-overleaf-package.zip
```

ZIP 路径必须是新的、不存在的路径，脚本不会覆盖已有 ZIP。不要把密码、私钥或 `SSHPASS` 写进脚本、论文、日志或 ZIP。

### 第六步：最终人工检查

重点检查：

- 结果文字是否同时报告获胜和非获胜条件；
- 是否误称为 universal SOTA 或实验验证；
- Figure 2/3 图注中的 `n=15`、均值 ± 样本标准差和数据来源是否准确；
- 图中 SVG/PDF 文字是否可编辑；
- 期刊要求的图尺寸和字体是否满足；
- Data Availability 是否符合真实数据许可；
- 所有作者是否确认作者顺序、声明和最终图表。

## 7. 不要做的事情

- 不要手工修改数字结果、表格或自动生成的 Results/Abstract/Discussion/Conclusion。
- 不要把历史监控快照中的部分 B5 数字当成当前状态；以最终审计摘要和正式审计输出为准。
- 不要把合成回归测试、缓存等价性测试或工程吞吐测试写成模型性能结果。
- 不要因为 GPU 空闲或单个日志时间较旧就重启已经完成的实验。
- 不要添加未经批准的外部基线、额外随机划分或测试集选择逻辑，并混入当前主结果。
- 不要把训练标签、测试标签或候选 pair 信息泄漏到 S1/S2 特征构建中。
- 不要将原始数据仓库的软件许可证直接解释为数据再分发许可证。

## 8. 交接完成标准

学生完成交接的最低标准是：

- `SUBMISSION_METADATA.md` 已由作者确认；
- 数据来源、版本和再分发条款已记录；
- 代码仓库和结果归档 URL/DOI 已确定；
- 两个独立审计命令再次通过；
- 最终 PDF 全部页面检查通过；
- 新 Overleaf ZIP 成功生成且不覆盖旧文件；
- 最终版本中的数值、图、表、source data 和文字来自同一份审计结果。

